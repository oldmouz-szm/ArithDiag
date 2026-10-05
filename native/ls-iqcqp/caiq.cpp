#include "sol.h"
#include <boost/multiprecision/cpp_int.hpp>
#include <fstream>
#include <iomanip>
#include <set>
namespace solver {
using boost::multiprecision::cpp_int;
static bool big(Float x,cpp_int &out) {
    if(!std::isfinite(x)||std::floor(x)!=x)return false;
    std::ostringstream s;s<<std::fixed<<std::setprecision(0)<<x;
    try {out=cpp_int(s.str());return true;}catch(...){return false;}
}
static cpp_int val(const caiq_equation &e,const std::vector<cpp_int> &x) {
    cpp_int r=0;
    for(auto &t:e.terms){cpp_int z(t.coefficient);for(int n:t.vars)z*=x[n];r+=z;}
    return r;
}
static bool solve(const caiq_equation &e,int pivot,std::vector<cpp_int> &x,qp_solver &q) {
    cpp_int a=0,b=0;
    for(auto &t:e.terms) {
        cpp_int z(t.coefficient);int degree=0;
        for(int n:t.vars){if(n==pivot)degree++;else z*=x[n];}
        if(degree>1)return false;
        if(degree)a+=z;else b+=z;
    }
    cpp_int target=cpp_int(e.rhs)-b,lo,hi;
    if(a==0||target%a!=0)return false;
    cpp_int y=target/a;
    if(!big(q._vars[pivot].lower,lo)||!big(q._vars[pivot].upper,hi)||y<lo||y>hi)return false;
    x[pivot]=y;return true;
}
void qp_solver::caiq_load(const char *path) {
    std::ifstream f(path);if(!f)throw std::runtime_error("CAIQ metadata unavailable");
    string tag;
    while(f>>tag) {
        if(tag=="MODE"){f>>caiq_enabled;}
        else if(tag=="I"){
            string name,value;f>>name>>value;
            if(!_vars_map.count(name))throw std::runtime_error("Unknown initial variable");
            Float native=std::stold(value);cpp_int exact;
            if(!big(native,exact)||exact!=cpp_int(value))throw std::runtime_error("Initial integer cannot be represented");
            caiq_initial[_vars_map.at(name)]=native;
        } else if(tag=="E") {
            string ab,rhs;int count;f>>ab>>rhs>>count;
            caiq_equation e;e.ab=ab=="-"?-1:_vars_map.at(ab);e.rhs=rhs;
            for(int i=0;i<count;i++){
                caiq_term t;int k;f>>t.coefficient>>k;
                for(int j=0;j<k;j++){string name;f>>name;t.vars.push_back(_vars_map.at(name));}
                e.terms.push_back(t);
            }
            caiq_equations.push_back(e);
        } else throw std::runtime_error("Invalid CAIQ metadata token");
    }
}
void qp_solver::caiq_initialise(){for(auto &p:caiq_initial)_init_solution_map[p.first]=p.second;}

bool qp_solver::caiq_step() {
    if(!caiq_enabled||caiq_equations.empty())return false;
    auto base=(caiq_state.size()==_vars.size() && rand()%5!=0)?caiq_state:(_best_assignment.size()==_vars.size()?_best_assignment:_cur_assignment);
    std::vector<cpp_int> original;
    for(Float z:base){cpp_int n;if(!big(z,n))return false;original.push_back(n);}
    std::vector<int> candidate;
    for(size_t i=0;i<caiq_equations.size();i++)if(caiq_equations[i].ab>=0&&original[caiq_equations[i].ab]!=0)candidate.push_back(i);
    if(candidate.empty())return false;
    for(int trial=0;trial<4;trial++){
        caiq_attempts++;
        auto x=original;
        auto &e=caiq_equations[candidate[rand()%candidate.size()]];
        bool moved=false;
        if(e.terms.size()==1&&e.terms[0].vars.size()==2&&e.terms[0].vars[0]!=e.terms[0].vars[1]){
            auto &t=e.terms[0];int a=t.vars[0],b=t.vars[1];
            cpp_int k(t.coefficient),target(e.rhs),al,ah,bl,bh;
            if(k!=0&&target%k==0&&big(_vars[a].lower,al)&&big(_vars[a].upper,ah)&&big(_vars[b].lower,bl)&&big(_vars[b].upper,bh)){
                target/=k;
                std::vector<std::pair<cpp_int,cpp_int>> pairs;
                if(target==0){
                    if(al<=0&&ah>=0)pairs.push_back({0,x[b]});
                    if(bl<=0&&bh>=0)pairs.push_back({x[a],0});
                }else if(target>0&&ah-al<=4096){
                    for(cpp_int d=std::max(cpp_int(1),al);d<=ah;d++){
                        if(target%d==0){cpp_int y=target/d;if(y>=bl&&y<=bh)pairs.push_back({d,y});}
                    }
                }else if(target>0){
                    for(int d=1;d<=20000;d++){
                        if(cpp_int(d)*d>target)break;
                        if(target%d==0){
                            cpp_int y=target/d;
                            if(d>=al&&d<=ah&&y>=bl&&y<=bh)pairs.push_back({d,y});
                            if(y>=al&&y<=ah&&d>=bl&&d<=bh)pairs.push_back({y,d});
                        }
                    }
                }
                if(!pairs.empty()){
                    std::vector<std::pair<cpp_int,cpp_int>> close;
                    for(auto &p:pairs)if(p.first==x[a]||p.second==x[b])close.push_back(p);
                    auto &pool=(!close.empty()&&rand()%2==0)?close:pairs;
                    auto p=pool[rand()%pool.size()];x[a]=p.first;x[b]=p.second;moved=true;
                }
            }
        }
        if(!moved){
            std::vector<int> pivots;
            for(auto &t:e.terms)for(int n:t.vars)if(std::find(pivots.begin(),pivots.end(),n)==pivots.end())pivots.push_back(n);
            if(pivots.empty())continue;
            int start=rand()%pivots.size();
            for(size_t j=0;j<pivots.size();j++)if(solve(e,pivots[(j+start)%pivots.size()],x,*this)){moved=true;break;}
        }
        if(!moved||x==original)continue;
        // Repair only unconditional wiring and components proved healthy by reduction.
        bool ok=true;
        for(int pass=0;pass<8;pass++){
            bool changed=false;
            for(auto &w:caiq_equations)if(w.ab<0&&val(w,x)!=cpp_int(w.rhs)){
                bool repaired=false;
                for(auto &t:w.terms)if(t.vars.size()==1&&solve(w,t.vars[0],x,*this)){repaired=true;changed=true;break;}
                if(!repaired){ok=false;break;}
            }
            if(!ok||!changed)break;
        }
        if(!ok)continue;
        // For fixed signals, weak faults permit the least AB assignment directly.
        for(auto &w:caiq_equations){
            if(w.ab<0){if(val(w,x)!=cpp_int(w.rhs)){ok=false;break;}}
            else x[w.ab]=(val(w,x)!=cpp_int(w.rhs))?1:0;
        }
        if(!ok)continue;
        // Check every native row exactly as integers, including certified cuts.
        for(auto &c:_constraints){
            cpp_int lhs=0,bound;
            if(!big(c.bound,bound)){ok=false;break;}
            for(auto &t:c.monomials){
                cpp_int z;if(!big(t.coeff,z)){ok=false;break;}
                for(int n:t.m_vars)z*=x[n];lhs+=z;
            }
            if(!ok|| (c.is_equal?lhs!=bound:c.is_less?lhs>bound:lhs<bound)){ok=false;break;}
        }
        if(!ok)continue;
        cpp_int obj=0;for(int n:_vars_in_obj)obj+=x[n];
        cpp_int best;
        if(_best_assignment.size()==_vars.size()&&big(_best_object_value,best)){
            cpp_int current=0;for(int n:_vars_in_obj)current+=original[n];
            if(obj>best+2)continue;
            if(obj>current && !(obj==current+1?rand()%4==0:rand()%16==0))continue;
        }
        std::vector<Float> native;
        for(size_t i=0;i<x.size();i++){
            Float z=x[i].convert_to<Float>();cpp_int back,lo,hi;
            if(!big(z,back)||back!=x[i]||!big(_vars[i].lower,lo)||!big(_vars[i].upper,hi)||x[i]<lo||x[i]>hi){ok=false;break;}
            native.push_back(z);
        }
        if(!ok||native==_cur_assignment)continue;
        caiq_accepted++;
        cout<<"\nCAIQSTATS "<<caiq_attempts<<" "<<caiq_accepted<<endl;
        caiq_state=native;
        _cur_assignment=native;
        _unbounded_constraints.clear();_unsat_constraints.clear();
        for(auto &c:_constraints){
            Float sum=0;for(auto &t:c.monomials)sum+=pro_mono(t);
            c.value=sum;pro_con_mix(&c);
        }
        is_cur_feasible=_unsat_constraints.empty();
        if(is_cur_feasible){is_feasible=true;_object_weight=1;update_best_solution();}
        return true;
    }
    return false;
}
}
