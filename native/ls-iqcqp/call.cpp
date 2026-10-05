#include "sol.h"
#include <limits>
namespace solver {
string mbd_num(Float x) {
    std::ostringstream stream;
    if(std::isfinite(x) && std::floor(x)==x) stream<<std::fixed<<std::setprecision(0)<<x;
    else stream<<std::setprecision(std::numeric_limits<Float>::max_digits10)<<x;
    return stream.str();
}
void qp_solver::mbd_emit() {
    if(!mbd_trace || _best_assignment.size()!=_vars.size() || _best_object_value>=mbd_last_emitted) return;
    auto start=std::chrono::steady_clock::now();
    mbd_last_emitted=_best_object_value;
    cout << "\nMBDTRACE {\"kind\":\"incumbent\",\"solver_s\":" << std::setprecision(17) << TimeElapsed()
         << ",\"objective\":\"" << mbd_num(_best_object_value+_obj_constant)
         << "\",\"values\":{";
    for(size_t j=0;j<_vars.size();j++) {
        if(j)cout<<",";
        cout << "\"" << _vars[j].name << "\":\"" << mbd_num(_best_assignment[j]) << "\"";
    }
    cout << "}}" << endl;
    mbd_trace_overhead += std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
}
void qp_solver::mbd_dump() {
    cout << std::setprecision(std::numeric_limits<Float>::max_digits10) << "{\"variables\":[";
    for(size_t i=0;i<_vars.size();i++) {
        auto &v=_vars[i];if(i)cout<<",";
        cout<<"{\"name\":\""<<v.name<<"\",\"type\":\""<<(v.is_bin?"binary":v.is_int?"integer":"continuous")
            <<"\",\"lb\":\""<<mbd_num(v.lower)<<"\",\"ub\":\""<<mbd_num(v.upper)<<"\"}";
    }
    cout << "],\"constraints\":[";
    for(size_t i=0;i<_constraints.size();i++) {
        auto &c=_constraints[i];if(i)cout<<",";
        cout<<"{\"name\":\""<<c.name<<"\",\"sense\":\""<<(c.is_equal?"eq":c.is_less?"le":"ge")
            <<"\",\"rhs\":\""<<mbd_num(c.bound)<<"\",\"monomials\":[";
        for(size_t j=0;j<c.monomials.size();j++){
            auto &m=c.monomials[j];if(j)cout<<",";
            cout<<"{\"coef\":\""<<mbd_num(m.coeff)<<"\",\"vars\":[";
            for(size_t k=0;k<m.m_vars.size();k++){if(k)cout<<",";cout<<"\""<<_vars[m.m_vars[k]].name<<"\"";}
            if(!m.is_linear && !m.is_multilinear)cout<<",\""<<_vars[m.m_vars[0]].name<<"\"";
            cout<<"]}";
        }
        cout<<"]}";
    }
    cout<<"],\"objective\":[";
    for(size_t j=0;j<_object_monoials.size();j++){
        auto &m=_object_monoials[j];if(j)cout<<",";
        cout<<"{\"coef\":\""<<mbd_num(m.coeff)<<"\",\"vars\":[";
        for(size_t k=0;k<m.m_vars.size();k++){if(k)cout<<",";cout<<"\""<<_vars[m.m_vars[k]].name<<"\"";}
        cout<<"]}";
    }
    cout<<"],\"float_mantissa_bits\":"<<std::numeric_limits<Float>::digits<<"}"<<endl;
}
}
int main(int argc,char **argv) {
    if(argc==3 && string(argv[1])=="--audit") {
        solver::qp_solver q;q.read(argv[2]);q.mbd_dump();return 0;
    }
    if(argc==6 && string(argv[1])=="--component-probe"){
        solver::qp_solver q;q.read(argv[2]);q.seed_num=std::atoi(argv[4]);std::srand(q.seed_num);q.caiq_load(argv[3]);q.mbd_trace=true;
        q._start_time=std::chrono::steady_clock::now();q.sta_cons();q.caiq_initialise();q.restart_by_new_solution();
        for(int i=0;i<std::atoi(argv[5]);i++){q._steps=i;q.caiq_step();}
        q.mbd_emit();
        cout<<"\nCAIQPROBE "<<q.caiq_attempts<<" "<<q.caiq_accepted<<endl;return 0;
    }
    if(argc<4){std::cerr<<"cutoff tabu filename [seed] [trace]\n";return 2;}
    solver::qp_solver q;
    q.read(argv[3]);q._cut_off=std::atof(argv[1]);q.tabu_switch=std::atoi(argv[2]);
    q.seed_num=argc>4?std::atoi(argv[4]):1;
    q.mbd_trace=argc>5 && std::atoi(argv[5])!=0;
    std::srand(q.seed_num);
    if(q.tabu_switch)q.set_constraint_tabu_enabled(true);
    if(argc>6 && string(argv[6])!="none")q.caiq_load(argv[6]);
    q.local_search();q.mbd_emit();
    cout<<"\nMBDEND {\"elapsed_s\":"<<q.TimeElapsed()<<",\"component_attempts\":"<<q.caiq_attempts<<",\"component_accepted\":"<<q.caiq_accepted<<",\"trace_overhead_s\":"<<q.mbd_trace_overhead<<"}"<<endl;
}
