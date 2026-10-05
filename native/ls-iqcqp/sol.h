#pragma once

#include "util.h"
// #define DEBUG
// #define OUTPUT_PROCESS
namespace solver 
{
    struct equal_var
    {
        int real_index;
        int bool_index;
        Float constant;
        Float real_coeff;
        Float bool_coeff;
        bool has_bool;
        equal_var(int real_index_o,  Float real_coeff_o, int bool_index_o, Float bool_coeff_o, Float constant_o)
        {
            real_index = real_index_o;
            bool_index = bool_index_o;
            real_coeff = real_coeff_o;
            bool_coeff = bool_coeff_o;
            constant = constant_o;
            has_bool = true;
        }
        equal_var(int real_index_o,  Float real_coeff_o, Float constant_o)
        {
            real_index = real_index_o;
            bool_index = -1;
            real_coeff = real_coeff_o;
            bool_coeff = -1;
            constant = constant_o;
            has_bool = false;
        }
    };
    struct var {
        int                     index;
        Float                   lower = 0, upper, constant;
        bool                    has_lower = true, has_upper;
        string                  name;
        unordered_set<int>      constraints;
        unordered_map<int, int> constraints_score;//不用管
        int                     obj_score;//不用管
        bool                    is_bin;
        bool                    is_int;
        bool                    is_in_obj;
        bool                    is_constant;
        bool                    equal_bound = false;
        int                     bool_score;//不用管
        Float                   obj_quadratic_coeff; //constant  初始化为0
        vector<int>             obj_linear_coeff; //var index
        vector<Float>           obj_linear_constant_coeff; //constant
        Float                   obj_constant_coeff;  //constant 
        vector<int>             obj_monomials;//不用管
        int                     last_pos_step = -10;//TODO:
        int                     last_neg_step = -10;
        CircularQueue            * recent_value;
        vector<equal_var>       equal_pair;
        var(int o_index, string o_name) : index(o_index), name(o_name)
        {
            has_lower = true;
            has_upper = false;
            is_constant = false;
            is_bin = false;
            is_int = false;
            obj_constant_coeff = 0;
            obj_quadratic_coeff = 0;
            recent_value = new CircularQueue;
        }
    };

    struct monomial {
        vector<int>             m_vars;
        // vector<int>             exponent;
        Float                   coeff;
        Float                   value; // the value of this monomial，没有去更新，没用
        bool                    is_linear; //TODO:再想想有没有别的办法区别
        bool                    is_multilinear;
        monomial(int o_var, Float o_coeff, bool o_is_linear) 
        {
            m_vars.push_back(o_var);
            coeff = o_coeff;
            is_linear = o_is_linear;
            is_multilinear = false;
        }
        monomial(int o_var_1, int o_var_2, Float o_coeff, bool o_is_linear) 
        {
            m_vars.push_back(o_var_1);
            m_vars.push_back(o_var_2);
            coeff = o_coeff;
            is_linear = o_is_linear;
            is_multilinear = true;
        }
    };

    struct all_coeff {
        Float                     obj_quadratic_coeff; //constant  初始化为0
        vector<int>               obj_linear_coeff; //var index
        vector<Float>             obj_linear_constant_coeff; //constant
        Float                     obj_constant_coeff;  //constant
        all_coeff()
        {
            obj_quadratic_coeff = 0;
            obj_constant_coeff = 0;
        }
    };

    struct polynomial_constraint {
        vector<monomial>                monomials;
        Float                           value;//只需要知道这个就好，不用知道变量的截距变量
        Float                           bound;
        unordered_map<int, all_coeff>   var_coeff;//TODO:构建
        vector<int>                     p_bin_vars;//不用管
        string                          name;
        int                             weight = 1;
        int                             index;
        bool                            is_sat;
        bool                            is_equal = false;
        bool                            is_less = true;
        bool                            is_quadratic = false;
        bool                            is_average = true;
        bool                            is_linear;
        Float                           sum;
        int                             tabu_step = -10;
        // vector<int>                     p_vars;
        // vector<int>                     p_quadratic_coeff; //constant  初始化为0
        // vector<vector<int>>             p_linear_coeff; //var index
        // vector<int>                     p_linear_constant_coeff; //constant
        // vector<int>                     p_constant_coeff;  //constant
        // vector<vector<int>>             p_coeff_vars;
        // vector<vector<int>>             p_coeff_vars_exponent;
    };
    
    struct pair_vars{
        int var_1;
        int var_2;
        Float value_1;
        Float value_2;
        int cons_pos;
        pair_vars(int var_idx_1, int var_idx_2)
        {
            var_1 = var_idx_1;
            var_2 = var_idx_2;
            value_1 = INT32_MIN;
            value_2 = INT32_MIN;
            cons_pos = -1;  // 默认值
        }
        pair_vars(int var_idx_1, int var_idx_2, Float change_value_1, Float change_value_2)
        {
            var_1 = var_idx_1;
            var_2 = var_idx_2;
            value_1 = change_value_1;
            value_2 = change_value_2;
            cons_pos = -1;  // 默认值
        }
        pair_vars(int var_idx_1, int var_idx_2, int cons_pos_o)
        {
            var_1 = var_idx_1;
            var_2 = var_idx_2;
            value_1 = INT32_MIN;
            value_2 = INT32_MIN;
            cons_pos = cons_pos_o;
        }
        bool operator==(const pair_vars& other) const 
        {
            bool flag = (var_1 == other.var_2) && (var_2 == other.var_1);
            bool flag_2 = (var_1 == other.var_1) && (var_2 == other.var_2);
            return (flag || flag_2);
        }
    };


    struct caiq_term { string coefficient; vector<int> vars; };
    struct caiq_equation { int ab=-1; string rhs; vector<caiq_term> terms; };
    class qp_solver {
    public:
        int                                             tabu_switch;
        bool                                            no_cons_int_flag = false;
        int                                             top_cons_num = 10;  
        const Float                                     eb = 1e-6;                
        // const Float                                     eb = 0;          //ali eb = 0 
        //for mix search
        int                                             unsat_cls_num_with_real;
        int                                             unsat_cls_num_with_bool;
        int                                             unbounded_cls_num_with_real;
        int                                             unbounded_cls_num_with_bool;
        int                                             seed_num=1;
        Float mbd_last_emitted=INT32_MAX;
        bool mbd_trace=false;
        double mbd_trace_overhead=0;
        void mbd_emit();
        void mbd_dump();
        bool caiq_enabled=false;
        long long caiq_attempts=0,caiq_accepted=0;
        unordered_map<int,Float> caiq_initial;
        vector<caiq_equation> caiq_equations;
        vector<Float> caiq_state;
        void caiq_load(const char *path);
        void caiq_initialise();
        bool caiq_step();
        //var information
        int                                             cons_num_type; // <= 50 : 0      >50 : 1
        int                                             problem_type;
        // 0:纯布尔  1:布尔整数实数 2:布尔+实数 3：纯整数 4：整数实数 5：纯实数
        int                                             _var_num;
        int                                             _bool_var_num;
        int                                             _int_var_num;
        vector<var>                                     _vars;
        unordered_set<int>                              _bool_vars;//TODO:算分 改成size好一点
        unordered_set<int>                              _int_vars;
        unordered_map<string, int>                      _vars_map;
        vector<Float>                                   _cur_assignment;
        vector<Float>                                   _cur_delta;
        unordered_set<int>                              _vars_in_obj;  
        unordered_set<int>                              _obj_vars_in_unbounded_constraint;      
        unordered_set<int>                              _obj_bin_vars_in_unbounded_constraint;                                    
        //cons information 
        int                                             _cons_num = -1;
        vector<polynomial_constraint>                   _constraints;
        unordered_set<int>                              _unsat_constraints;
        unordered_set<int>                              _unbounded_constraints;
        int                                             _best_unsat_num;
        //obj information
        bool                                            is_minimize = true;
        Float                                           _obj_constant = 0;
        vector<monomial>                                _object_monoials;
        vector<int>                                     _object_weights;
        int                                             _object_weight;
        Float                                           _best_object_value = INT32_MAX;
        bool                                            is_obj_quadratic = false;
        bool                                            is_cons_quadratic = false;
        //solution information
        bool                                            print_flag = false;
        int                                             _best_steps;
        vector<Float>                                   _best_assignment;
        bool                                            is_feasible;
        bool                                            is_cur_feasible;
        //selection information
        vector<int>                                     _operation_vars;
        vector<Float>                                   _operation_value;
        vector<int>                                     _operation_vars_sub;// bin vars
        vector<Float>                                   _operation_value_sub; //bin value
        vector<int>                                     _operation_cons_pos;
        vector<pair_vars>                               _operation_vars_pair;//bin pair vars;
        
        // 约束级别的tabu机制
        bool                                            _constraint_tabu_enabled = false;  // tabu开关
        vector<int>                                     _rand_op_vars;
        vector<Float>                                   _rand_op_values;
        int                                             bms = 100;// 100 200
        const int                                       rand_num = 3;
        const int                                       rand_num_obj = 3;
        //ls information
        int                                             int_problem; // 0 means all real, 1 means mix, 2 means all int
        int                                             bin_problem; // 0 means all real, 1 means mix, 2 means all bool                                           
        int                                             _steps;
        const int                                       _max_steps = INT32_MAX;   
        std::chrono::steady_clock::time_point           _start_time;
        double                                          _cut_off = 300;
        //constant          
        Float                                           avg_bound = 0;
        //functions
        // bool                                            error_judge
        Float                                           pro_var_value_delta_in_obj_cy(var * nor_var, int var_pos, Float old_value, Float new_value);
        Float                                           calculate_score_cy(int var_idx, Float change_value);
        Float                                           calculate_score_cy_mix(int var_idx, Float change_value);
        bool                                            is_true_number(string str);
        //new
        //read func
        bool                                            bound_flag = false;
        void                                            split_string(string in_string, vector<std::string> &str_vec, string pattern);
        bool                                            isNumber(string str);
        Float                                           pro_coeff(string s_coeff);
        int                                             register_var(string s_var);
        void                                            read(char * filename);
        void                                            read_obj(string line);
        bool                                            with_quadratic = false;
        void                                            read_cons(string line);
        void                                            read_bounds(string line);
        void                                            read_int(string line);
        void                                            read_bin(string line);
        void                                            judge_problem();
        void                                            initialize();
        void                                            initialize_without_cons();
        void                                            initialize_mix();
        double                                          TimeElapsed();
        void                                            precess_small_ins();
        Float                                           pro_mono(monomial mono);
        Float                                           pro_mono_inc(monomial mono, int var_pos);
        void                                            pro_con(polynomial_constraint * pcon);
        void                                            pro_con_mix(polynomial_constraint * pcon);
        Float                                           pro_var_delta(var * bin_var, polynomial_constraint * pcon, int var_pos, bool is_pos);//bool
        Float                                           pro_var_value_delta(var * nor_var, polynomial_constraint * pcon, int var_pos, Float old_value, Float new_value);//int and real
        int                                             pro_var_delta_in_obj(var * bin_var, int var_pos, bool is_pos);
        int                                             pro_var_value_delta_in_obj(var * nor_var, int var_pos, Float old_value, Float new_value);
        Float                                           pro_var_delta_in_obj_cy(var * bin_var, int var_pos, bool is_pos);
        void                                            init_pro_con(polynomial_constraint * pcon);
        void                                            init_pro_con_mix(polynomial_constraint * pcon);
        int                                             judge_cons_state(polynomial_constraint * pcon, Float con_delta);//-1: sat->unsat  0: no change 1: unsat->sat 
        int                                             judge_cons_state_bin(polynomial_constraint * pcon, Float var_delta, Float con_delta);//-1: sat->unsat, unsat->more unsat; 0: no change or sat ->sat 1:unsat -> sat ,more unsat->unsat
        Float                                           judge_cons_state_bin_cy(polynomial_constraint * pcon, Float var_delta, Float con_delta);
        Float                                           judge_cons_state_mix(polynomial_constraint * pcon, Float var_delta, Float con_delta);//-1: sat->unsat  0: no change 1: unsat->sat 
        Float                                           judge_cons_state_bin_cy_mix(polynomial_constraint * pcon, Float var_delta, Float con_delta);
        bool                                            judge_bin_var_feasible(int var_idx, all_coeff * a_coeff, polynomial_constraint * pcon);
        //unsat state
        void                                            insert_operation_unsat();
        void                                            insert_operation_unsat_bin();
        void                                            insert_operation_unsat_mix();
        void                                            insert_operation_unsat_mix_not_dis();
        void                                            insert_var_change_value(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag);
        void                                            insert_var_change_value_bin(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag);
        void                                            random_walk_unsat();
        void                                            random_walk_unsat_bin();
        void                                            random_walk_unsat_mix(bool bin_flag);
        void                                            random_walk_unsat_mix_not_dis();
        void                                            no_operation_walk_unsat();
        //sat state
        void                                            insert_operation_sat();
        void                                            insert_operation_sat_bin();
        void                                            insert_operation_sat_bin_with_equal();
        void                                            insert_operation_sat_mix();
        void                                            insert_operation_sat_mix_not_dis();
        // void                                            insert_operation_sat_mix()
        void                                            insert_operation_no_cons();
        void                                            insert_var_change_value_sat(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, int symflag, Float symvalue, bool rand_flag);
        bool                                            insert_var_change_value_sat_bin(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, Float symvalue, bool rand_flag);
        bool                                            insert_var_change_value_sat_bin_equal(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, Float symvalue, bool rand_flag);
        void                                            random_walk_sat();
        void                                            random_walk_sat_bin();
        void                                            random_walk_sat_bin_with_equal();
        void                                            random_walk_sat_mix(bool bin_flag);
        void                                            random_walk_sat_mix_not_dis();
        void                                            random_walk_no_cons();
        void                                            no_operation_walk_sat(int var_idx);
        void                                            lift_move_op(int var_idx, Float & score);//only for bool, 约束少的时候要用吗还是都用？
        int                                             lift_move();
        bool                                            two_flip_no_cons();
        bool                                            fps_move();
        void                                            no_bound_sat_move();
        //new balance op
        bool                                            insert_var_change_value_balance(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, Float symvalue, bool rand_flag);
        bool                                            insert_var_change_value_balance_rf(int var_idx, polynomial_constraint * pcon, int symflag, Float symvalue, bool rand_flag);
        void                                            insert_operation_balance();
        void                                            random_walk_balance();
        void                                            local_search_mix_balance();
        
        // 约束tabu相关函数
        void                                            set_constraint_tabu_enabled(bool enabled);
        bool                                            is_constraint_tabu(int constraint_idx);
        
        //new compensate operators
        bool                                            compensate_move();
        void                                            insert_var_change_value_comp(int var_pos, Float change_value, int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag);
        void                                            insert_var_change_value_comp_bin(int var_pos, Float change_value, int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag);
        Float                                           calculate_score_compensate_cons_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2, bool is_distance);
        Float                                           calculate_cons_descent_two_vars_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2, polynomial_constraint * pcon);
        Float                                           calculate_obj_descent_two_vars_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2);
        void                                            select_best_operation_with_pair_mix(int & var_idx_1, Float & change_value_1, int & var_idx_2, Float & change_value_2, Float & score);
        // Float                                           calculate_var_best_value(var * nor_var, int var_pos, int & change_flag); //1 up, 0 quad, -1 down;                                                    
        //ususal in search
        Float                                           calculate_cons_descent_two_vars(int var_idx_1, int var_idx_2, polynomial_constraint * pcon);
        Float                                           calculate_obj_descent_two_vars(int var_idx_1, int var_idx_2);
        Float                                           calculate_score_compensate_cons(int var_idx_1, int var_idx_2);
        Float                                           calculate_coeff_in_obj(int var_idx);
        Float                                           calculate_score(int var_idx, Float change_value);
        Float                                           calculate_score_bin(int var_idx, Float change_value);
        Float                                           calculate_score_bin_cy(int var_idx, Float change_value);
        Float                                           calculate_score_no_cons(int var_idx, Float change_value);//no meas a few ir 0
        Float                                           calculate_score_mix(int var_idx, Float change_value);
        Float                                           is_lift(int var_idx, Float change_value);
        Float                                           obj_lift(int var_idx, Float change_value);
        void                                            select_best_operation(int & var_pos, Float & change_value, Float & score);
        void                                            select_best_operation_bin(int & var_pos, Float & change_value, Float & score);
        void                                            select_best_operation_bin_with_pair(int & var_pos_1, int & var_pos_2, Float & change_value, Float & score);
        void                                            select_best_operation_no_cons(int & var_pos, Float & change_value, Float & score);
        void                                            select_best_operation_mix(int & var_pos, Float & change_value, Float & score);
        void                                            select_best_operation_lift(int & var_pos, Float & change_value, Float & score);
        bool                                            check_var_shift(int var_pos, Float & change_value, bool rand_flag);
        bool                                            check_var_shift(int var_pos, double & change_value, bool rand_flag);
        bool                                            check_var_shift_bool(int var_pos, Float & change_value, bool rand_flag);
        void                                            execute_critical_move(int var_pos, Float change_value);
        void                                            execute_critical_move_no_cons(int var_pos, Float change_value);
        void                                            execute_critical_move_mix(int var_pos, Float change_value);
        void                                            execute_critical_move_mix_more(int var_pos, Float change_value);
        void                                            update_weight();
        void                                            update_weight_no_cons();
        void                                            update_best_solution();
        // Float                                           up_down_float(Float symvalue);
        void                                            local_search_with_real(); //real may exist integer
        void                                            local_search_bin(); //bin only , for qcp
        void                                            local_search_bin_new(); //bin only with equal  for qp
        void                                            local_search_mix();//real bin may exists integer
        void                                            local_search_mix_not_dis();
        void                                            local_search_without_cons();
        void                                            local_search();
        //cout 
        int                                             sta_mix_cons();
        void                                            print_formula();
        void                                            print_cons(int cons_idx);
        void                                            print_mono(monomial mono);
        void                                            print_imp_info();
        void                                            print_best_solution();
        void                                            print_lp_formula(bool is_all_obj);
        // bool                                            print_lp_cons(int cons_idx, bool is_first, bool & is_quad);
        bool                                            print_lp_mono(monomial mono, bool is_first, bool & is_quad, bool is_obj);
        int                                             read_init_solution(char * filename);
        unordered_set<int>                              print_vars; 
        std::vector<monomial>                           print_bounded_objs;
        unordered_map<int, Float>                       _init_solution_map;  
        void                                            restart_by_new_solution();
        void                                            print_bounded_obj();  
        void                                            select_bounded_mono();   
        void                                            add_bool_bound();                 
        void                                            sta_cons();
        // propagation
        class propagation;
        friend class propagation;
        propagation*                                    _propagationer;
    };
}
