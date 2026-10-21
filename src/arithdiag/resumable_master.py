"""Exact-family resumable search for the auxiliary positive hitting-set problem.

DFS frames and proved residual UNSAT states survive time/node slices. New edge
families use separate sessions. No circuit feasibility is inferred here.
"""
from collections import OrderedDict
from dataclasses import dataclass
import time
from arithdiag import hitting_set as h

SESSIONS=OrderedDict()
METRICS=dict(resumable_sessions=0,resumable_hits=0,resumable_pauses=0,
    resumable_nodes=0,resumable_completed_queries=0)

@dataclass
class Frame:
    remaining:int
    k:int
    chosen:tuple
    choices:list|None=None
    index:int=0

class Session:
    def __init__(self,edges,deadline):
        self.edges=edges
        self.engine=h._Engine(edges,h._Budget(deadline,None))
        self.lower=0;self.upper=len(self.engine.covers)
        self.cover=frozenset(self.engine.representatives.values())
        self.initialized=False;self.goal=None;self.stack=[]

    def decision(self,k,budget):
        e=self.engine;e.budget=budget
        if self.goal!=k:
            self.goal=k;self.stack=[Frame(e.full,k,())]
        while self.stack:
            budget.check()
            frame=self.stack[-1]
            if frame.choices is None:
                # Nothing is removed before the interruptible analysis finishes.
                budget.check(visit=True)
                rem,left=frame.remaining,frame.k
                if not rem:
                    result=frozenset(e.representatives[c] for c in frame.chosen)
                    budget.check();self.stack=[];self.goal=None
                    return 'SAT',result
                if left<=0 or e.unsat.get(rem,-1)>=left:
                    self.stack.pop();continue
                index=next(i for i in e.edge_order if rem&(1<<i))
                originals={}
                for cover in e.by_edge[index]:originals.setdefault(cover&rem,cover)
                masks=sorted(originals,key=lambda mask:(-mask.bit_count(),mask))
                maximal=[];immediate=None
                for mask in masks:
                    budget.check()
                    if mask==rem:immediate=originals[mask];break
                    if not any(mask&other==mask for other in maximal):maximal.append(mask)
                if immediate is not None:
                    result=frozenset(e.representatives[c] for c in frame.chosen+(immediate,))
                    budget.check();self.stack=[];self.goal=None
                    return 'SAT',result
                threshold=(rem.bit_count()+left-1)//left
                impossible=e.packing(rem)>left
                if not impossible:
                    impossible=not any((cover&rem).bit_count()>=threshold for cover in e.covers)
                if impossible:
                    e.unsat[rem]=max(left,e.unsat.get(rem,-1));self.stack.pop();continue
                frame.choices=[originals[mask] for mask in maximal]
            elif frame.index<len(frame.choices):
                cover=frame.choices[frame.index];frame.index+=1
                self.stack.append(Frame(frame.remaining&~cover,frame.k-1,frame.chosen+(cover,)))
            else:
                e.unsat[frame.remaining]=max(frame.k,e.unsat.get(frame.remaining,-1))
                if len(e.unsat)>65536:e.unsat.clear()
                self.stack.pop()
        self.goal=None
        return 'UNSAT',None

def clear():
    SESSIONS.clear()

def improve(conflicts,current_lower=0,*,target_upper=None,deadline=None,max_nodes=None,on_candidate=None):
    h._validate_limit(max_nodes,'max_nodes')
    started=time.monotonic();edges=h._normalise(conflicts)
    budget=h._Budget(deadline,max_nodes);session=None;exact=False;low=0;upper=None
    status='UNKNOWN';evidence='resumable_exact_family_conflict_cover';infeasible=False
    try:
        budget.check()
        if edges and not edges[0]:
            infeasible=True;exact=True;status='INFEASIBLE'
        elif not edges:
            low=upper=0;exact=True;status='SAT'
            if on_candidate is not None:on_candidate(frozenset())
        else:
            key=frozenset(edges)
            if key not in SESSIONS:
                session=Session(edges,deadline);SESSIONS[key]=session;METRICS['resumable_sessions']+=1
                while len(SESSIONS)>16:SESSIONS.popitem(last=False)
            else:
                session=SESSIONS[key];SESSIONS.move_to_end(key);METRICS['resumable_hits']+=1
            e=session.engine;e.budget=budget
            if not session.initialized:
                # Greedy upper and dual packing do not need DFS-node credit.
                greedy=e.greedy_upper()
                cover=frozenset(e.representatives[c] for c in e.greedy_solution)
                session.upper=greedy;session.cover=cover
                session.lower=max(session.lower,e.packing(e.full))
                session.initialized=True
            session.lower=max(session.lower,current_lower)
            if session.lower>session.upper:raise ValueError('Reliable cover bound exceeds verified cover')
            low,upper=session.lower,session.upper
            if on_candidate is not None:
                budget.check();on_candidate(session.cover)
            while session.lower<session.upper and (target_upper is None or session.lower<target_upper):
                status,cover=session.decision(session.lower,budget)
                METRICS['resumable_completed_queries']+=1
                if status=='UNSAT':session.lower+=1
                else:
                    if any(not cover.intersection(edge) for edge in session.edges):raise ValueError('Invalid resumed cover')
                    session.upper=min(session.upper,len(cover));session.cover=cover
                    if on_candidate is not None:
                        budget.check();on_candidate(cover)
            low,upper=session.lower,session.upper;exact=low==upper
            if exact:status='SAT'
    except h._Stopped:
        METRICS['resumable_pauses']+=1
    finally:
        METRICS['resumable_nodes']+=budget.nodes
    if session is not None:
        low,upper=session.lower,session.upper
        # Completed arithmetic facts may survive a pause, but late completion
        # is not advertised as an exact optimization result.
        exact=low==upper and (deadline is None or time.monotonic()<deadline)
    return dict(lower_bound=max(current_lower,low),conflict_lower_bound=low,
        auxiliary_upper_bound=upper,exact=exact,infeasible=infeasible,
        checked_up_to=low-1 if low else None,last_status=status,evidence=evidence,
        nodes=budget.nodes,decisions=0,reason=budget.reason,elapsed_s=time.monotonic()-started,
        conflict_count=len(edges))

def greedy_proposal(conflicts,maximum,deadline=None):
    """A cover proposal only; size>goal never establishes SAT for that goal."""
    edges=h._normalise(conflicts)
    if edges and not edges[0]:return None
    if deadline is not None and time.monotonic()>=deadline:return None
    if not edges:return frozenset()
    by_vertex={}
    for i,edge in enumerate(edges):
        for v in edge:by_vertex[v]=by_vertex.get(v,0)|(1<<i)
    remaining=(1<<len(edges))-1;chosen=[]
    while remaining and len(chosen)<=maximum:
        if deadline is not None and time.monotonic()>=deadline:return None
        v=max(by_vertex,key=lambda n:(by_vertex[n]&remaining).bit_count())
        chosen.append(v);remaining&=~by_vertex[v]
    if remaining or len(chosen)>maximum:return None
    cover=frozenset(chosen)
    if any(not cover.intersection(edge) for edge in edges):raise ValueError('Invalid proposal')
    return cover
