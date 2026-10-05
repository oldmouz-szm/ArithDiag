#include "sol.h"
namespace solver
{

    void qp_solver::precess_small_ins()
    {
        var * obj_var;
        for (int var_pos : _vars_in_obj)
        {
            obj_var = & (_vars[var_pos]);
            obj_var->obj_constant_coeff *= 10000000;
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                obj_var->obj_linear_constant_coeff[linear_pos] *= 10000000;
            }
        }
        for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
        {
            _object_monoials[mono_pos].coeff *= 10000000;
        }
    }

    void qp_solver::local_search_bin_new()
    {
        std::srand(seed_num);
        initialize();
        // exit(0);
        // precess_small_ins();
        int var_pos, var_pos_equal_1, var_pos_equal_2;
        int lift_var;
        Float change_value, score, change_value_not_used, score_equal, max_score;
        for (_steps = 0; _steps <= _max_steps; _steps++)
        {
            //TODO
#ifdef DEBUG
            cout << " unsat num: "  << _unsat_constraints.size()  << endl;
#endif
            if (_steps % 1000 == 0 && (TimeElapsed() > _cut_off)) 
            {
                if (print_flag) cout << "steps = " << _steps << endl;
                break;
            }
            if (is_cur_feasible)
            {
                insert_operation_sat_bin_with_equal();
                select_best_operation_bin(var_pos, change_value, score);
                select_best_operation_bin_with_pair(var_pos_equal_1, var_pos_equal_2, change_value_not_used, score_equal);
                max_score = std::max(score, score_equal);
                if (max_score > 0) 
                {
#ifdef DEBUG
                    cout << " sat greedy walk " << endl;
#endif
                    if (score > 0 || max_score == score)
                        execute_critical_move(var_pos, change_value);
                    else 
                    {
                        Float change_value_1 = (_cur_assignment[var_pos_equal_1] == 0) ? 1 : -1;
                        Float change_value_2 = (_cur_assignment[var_pos_equal_2] == 0) ? 1 : -1;
                        execute_critical_move(var_pos_equal_1, change_value_1);
                        execute_critical_move(var_pos_equal_2, change_value_2);
                    }
                }
                else 
                {
                    update_weight();
                    random_walk_sat_bin_with_equal();
                }
            }
            else 
            {
                insert_operation_unsat_bin();
                select_best_operation_bin(var_pos, change_value, score);
                if (score > 0) 
                {
#ifdef DEBUG
                cout << " unsat greedy walk " << endl;
#endif
                    execute_critical_move(var_pos, change_value);
                }
                else 
                {
                    update_weight();
                    random_walk_unsat_bin();
                }
            }
        }
        // _best_object_value /= 10000000;
        if (print_flag) cout << " best steps = " << _best_steps << endl;
        if (_best_object_value == INT32_MAX) 
        {
            cout << " best obj min= " ;
            cout << INT32_MAX << endl;
        }
        else
        {
            if (is_minimize)
                cout << std::fixed << " best obj min= " ;
            else 
                cout << std::fixed << " best obj max= " ;
            if (is_minimize) cout << _best_object_value + _obj_constant;
            else cout << -_best_object_value + _obj_constant;
            // cout << endl << " solution : " <<endl;
            // print_best_solution();
        } 
    }

    void qp_solver::random_walk_sat_bin_with_equal()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        var * obj_var;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        int li_var_idx;
        Float best_value;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_vars_pair.clear();
        _operation_cons_pos.clear();
        int no_operation_var = rand() % _vars.size();
        unordered_set<int> rand_obj_idx;
        bool is_bool;
        int op_num;
        Float cur_value, change_value;
        if (_obj_vars_in_unbounded_constraint.size() == 0)
        {
            // cout << " _obj_vars_in_unbounded_constraint.size() = 0  error " << endl;
            // exit(0);
            no_bound_sat_move();
            return;
        }
        for (int i = 0; i < rand_num_obj; i++) 
        {
            unordered_set<int>::iterator it(_obj_vars_in_unbounded_constraint.begin());
            std::advance(it, rand() % _obj_vars_in_unbounded_constraint.size());
            rand_obj_idx.insert(*it);
            if (i == 0) no_operation_var = *it; 
        }
        for (int var_pos : rand_obj_idx)
        {
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            change_value = (cur_value == 0) ? 1 : -1;
            linear_coeff_value = obj_var->obj_constant_coeff;
            op_num = _operation_vars_sub.size();
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            }
            linear_coeff_value += obj_var->obj_quadratic_coeff;
            if (linear_coeff_value == 0) continue;
            if (linear_coeff_value > 0 && cur_value == 0) continue;
            if (linear_coeff_value < 0 && cur_value == 1) continue;
            for (int con_pos: obj_var->constraints)
            {
                unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                a_coeff = &(unbound_con->var_coeff[var_pos]);
                if (unbound_con->is_equal) 
                    insert_var_change_value_sat_bin_equal(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false);  
                else if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false); //TODO:check
            }
        }
        int var_pos;
        Float change_value_2, score;
        select_best_operation_bin(var_pos, change_value_2, score);
        int var_pos_equal_1, var_pos_equal_2;
        Float score_equal, change_value_equal, max_score;
        select_best_operation_bin_with_pair(var_pos_equal_1, var_pos_equal_2, change_value_equal, score_equal);
        max_score = std::max(score, score_equal);
        if (max_score != INT32_MIN) 
        {
#ifdef DEBUG
            cout << " sat random walk " << endl;
#endif
            if (max_score == score)
                execute_critical_move(var_pos, change_value_2);
            else 
            {
                Float change_value_2 = (_cur_assignment[var_pos_equal_1] == 0) ? 1 : -1;
                Float change_value_3 = (_cur_assignment[var_pos_equal_2] == 0) ? 1 : -1;
                execute_critical_move(var_pos_equal_1, change_value_2);
                execute_critical_move(var_pos_equal_2, change_value_3);
            }
        }
        else 
        {
#ifdef DEBUG
            cout << " unsat random walk " << endl;
#endif
            Float value = (_cur_assignment[no_operation_var] == 0) ? 1 : -1;
            if (check_var_shift_bool(no_operation_var, value, 1)) execute_critical_move(no_operation_var, value);
        }
    }

    void qp_solver::select_best_operation_bin_with_pair(int & var_pos, int & var_pos_2, Float & change_value, Float & score)
    {
        //select 和random walk 要大改，ls函数也要改参数等
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars_pair.size();
        // 确保数组大小一致
        // if (op_size != _operation_cons_pos.size())
        // {
        //     cout << "Error: _operation_vars_pair.size() = " << op_size 
        //          << " != _operation_cons_pos.size() = " << _operation_cons_pos.size() << endl;
        //     cout << "Debug: This is in select_best_operation_bin_with_pair function" << endl;
        //     return;
        // }
        bool is_bms;
        if (op_size <= bms) 
        {
            cnt = op_size;
            is_bms = false;
        } 
        else 
        {
            cnt = bms;
            is_bms = true;
        }
        int cur_var, cur_var_2;
        Float cur_shift, cur_score;
        int rand_index, cons_pos = -1, cur_cons_pos;
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars_pair[rand_index].var_1;
                cur_var_2 = _operation_vars_pair[rand_index].var_2;
                cur_cons_pos = _operation_vars_pair[rand_index].cons_pos;
                _operation_vars_pair[rand_index] = _operation_vars_pair[op_size - i - 1];
                // _operation_cons_pos[rand_index] = _operation_cons_pos[op_size - i - 1];
                // _operation_value_sub[rand_index] = _operation_value_sub[op_size - i - 1];
            } 
            else {
                cur_var = _operation_vars_pair[i].var_1;
                cur_var_2 = _operation_vars_pair[i].var_2;
                cur_cons_pos = _operation_vars_pair[i].cons_pos;
            }
            if (is_cur_feasible)
                cur_score = calculate_score_compensate_cons(cur_var, cur_var_2);
            else 
            {
                cout << " not unsat but sat pair selection" << endl;
                exit(0);
            }
            if (cur_score > score) {
                score = cur_score;
                var_pos = cur_var;
                var_pos_2 = cur_var_2;
                cons_pos = cur_cons_pos;
            }
        }
        if (_constraint_tabu_enabled && cons_pos != -1)
        {
            _constraints[cons_pos].tabu_step = _steps + rand() % 10 + 3;
        }
    }

    void qp_solver::insert_operation_sat_bin_with_equal()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        int var_idx;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        Float change_value;
        int li_var_idx;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        int op_num;
        Float cur_value;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        _operation_vars_pair.clear();
        _obj_vars_in_unbounded_constraint.clear();
        
        // std::priority_queue<std::pair<int, int>> global_constraint_queue; // (weight, constraint_pos)
        // std::unordered_set<int> top_constraints; // 存储权重最高的10个约束位置
        
        // // 收集所有约束的权重
        // for (int var_pos : _vars_in_obj)
        // {
        //     obj_var = & (_vars[var_pos]);
        //     for (int con_pos: obj_var->constraints)
        //     {
        //         if (_constraints[con_pos].tabu_step > _steps) continue;
        //         int weight = (_constraints[con_pos]).weight;
        //         global_constraint_queue.push(std::make_pair(weight, con_pos));
        //     }
        // }
        
        // // 取出权重最高的10个约束
        // int constraint_count = 0;
        // while (!global_constraint_queue.empty() && constraint_count < top_cons_num)
        // {
        //     int con_pos = global_constraint_queue.top().second;
        //     global_constraint_queue.pop();
        //     top_constraints.insert(con_pos);
        //     constraint_count++; 
        // }


        for (int var_pos : _vars_in_obj)
        {
            op_num = _operation_vars_sub.size();
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            change_value = (cur_value == 0) ? 1 : -1;
            //execute the best value of objvar
            linear_coeff_value = obj_var->obj_constant_coeff;
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            }
            linear_coeff_value += obj_var->obj_quadratic_coeff;
            if (linear_coeff_value == 0) continue;
            if (linear_coeff_value > 0 && cur_value == 0) continue;
            if (linear_coeff_value < 0 && cur_value == 1) continue;
            if ((change_value > 0 && _steps <= _vars[var_pos].last_pos_step) || (change_value < 0 && _steps <= _vars[var_pos].last_neg_step)) continue;
            //这里有问题，如果是两个变量的话不一定根据一个变量去continue？，好像是避免重复了，好像也不是，因为有一些共作用的。一个布尔变量的是怎么变的？
            for (int con_pos: obj_var->constraints)
            {
                if (_constraints[con_pos].tabu_step > _steps) continue;
                // if (top_constraints.find(con_pos) == top_constraints.end())
                //     continue;
                unbound_con = & (_constraints[con_pos]);
                a_coeff = &(unbound_con->var_coeff[var_pos]);
                if (unbound_con->is_equal) 
                {
                    if (insert_var_change_value_sat_bin_equal(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false));
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                }
                // else if (linear_coeff_value == 0) continue;
                // else if (linear_coeff_value > 0 && cur_value == 0) continue;
                // else if (linear_coeff_value < 0 && cur_value == 1) continue;
                else if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                {
                    // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                    if (insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false)) //TODO:check
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                    
                }
            }
        }
    }

    bool qp_solver::insert_var_change_value_sat_bin_equal(int var_idx, all_coeff * a_coeff, Float delta_unused, polynomial_constraint * pcon, Float symvalue, bool rand_flag)
    {
        //这个函数写好，想好在哪里用
        //两个变量都在目标函数的情况，一个在一个不在
        //进这个函数的条件是目标变量一定能让目标函数下降
        all_coeff * obj_var_coeff = &(pcon->var_coeff[var_idx]);
        Float change_value = (_cur_assignment[var_idx] == 0) ? 1 : -1;
        Float delta = obj_var_coeff->obj_constant_coeff * change_value;
        Float sub_change_value, sub_delta;
        bool is_have = false;
        // if ((change_value > 0 && _steps <= _vars[var_idx].last_pos_step) || (change_value < 0 && _steps <= _vars[var_idx].last_neg_step)) return false;
        for (auto coeff : pcon->var_coeff)
        {
            //没有更特化的处理，比如直接找a+b+c=1的或者全部都是0的过滤的操作，给这样的约束预先打上tag，方便这里处理！！
            if (coeff.first == var_idx) continue;
            sub_change_value = (_cur_assignment[coeff.first] == 0) ? 1 : -1;
            // if ((sub_change_value > 0 && _steps <= _vars[coeff.first].last_pos_step) || (sub_change_value < 0 && _steps <= _vars[coeff.first].last_neg_step)) return false; 
            sub_delta = sub_change_value * coeff.second.obj_constant_coeff;
            if (sub_delta + delta == 0)
            {
                if (!_vars[coeff.first].is_in_obj || calculate_obj_descent_two_vars(var_idx, coeff.first) < 0)
                {
                    //insert ，暂时没有加入tabu这个元素
                    // if (check_var_shift_bool(var_idx, change_value, rand_flag))
                    // if ((sub_change_value > 0 && _steps <= _vars[coeff.first].last_pos_step + 1) || (sub_change_value < 0 && _steps <= _vars[coeff.first].last_neg_step + 1)) return false; 
                    pair_vars cur(var_idx, coeff.first, pcon->index);
                    if (true)
                    {
                        _operation_vars_pair.push_back(cur);
                        // _operation_cons_pos.push_back(pcon->index);
                        is_have = true;
                    }
                }
            }
        }
        return is_have;
    }

    Float qp_solver::calculate_cons_descent_two_vars(int var_idx_1, int var_idx_2, polynomial_constraint * pcon)
    {
        var * var_1 = &(_vars[var_idx_1]);
        var * var_2 = &(_vars[var_idx_2]);
        all_coeff * coeff_1 = &(pcon->var_coeff[var_idx_1]); 
        all_coeff * coeff_2 = &(pcon->var_coeff[var_idx_2]);
        Float change_value_1 = (_cur_assignment[var_idx_1] == 0) ? 1 : -1;
        Float change_value_2 = (_cur_assignment[var_idx_2] == 0) ? 1 : -1;
        int li_var_idx;
        Float linear_coeff_value_1 = coeff_1->obj_constant_coeff + coeff_1->obj_quadratic_coeff;
        Float linear_coeff_value_2 = coeff_2->obj_constant_coeff + coeff_2->obj_quadratic_coeff;
        Float li_var_coeff;
        Float both_coeff = 0;
        for (int linear_pos = 0; linear_pos < coeff_1->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = coeff_1->obj_linear_coeff[linear_pos];
            li_var_coeff = coeff_1->obj_linear_constant_coeff[linear_pos];
            if (li_var_idx != var_idx_2)
                linear_coeff_value_1 += _cur_assignment[li_var_idx] * li_var_coeff;
            else 
                both_coeff = li_var_coeff;
        }
        linear_coeff_value_1 *= change_value_1; 
        for (int linear_pos = 0; linear_pos < coeff_2->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = coeff_2->obj_linear_coeff[linear_pos];
            li_var_coeff = coeff_2->obj_linear_constant_coeff[linear_pos];
            if (li_var_idx != var_idx_1)
                linear_coeff_value_2 += _cur_assignment[li_var_idx] * li_var_coeff;
            else if (both_coeff != li_var_coeff)
                cout << " both error " << both_coeff << " " << li_var_coeff << endl;
        }
        linear_coeff_value_2 *= change_value_2; 
        if (change_value_1 == 1 && change_value_2 == 1) both_coeff = both_coeff;
        else if (change_value_1 != change_value_2) both_coeff = 0;
        else if (change_value_1 == -1 && change_value_2 == -1) both_coeff = - both_coeff;
        return linear_coeff_value_1 + linear_coeff_value_2 + both_coeff;
    }

    Float qp_solver::calculate_score_compensate_cons(int var_idx_1, int var_idx_2)
    {
        Float score = 0;
        score -= _object_weight * calculate_obj_descent_two_vars(var_idx_1, var_idx_2);
        return score;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float state;
        var * var_1;
        var * var_2;
        Float norm;
        var_1 = & (_vars[var_idx_1]);
        var_2 = & (_vars[var_idx_2]);
        unordered_set<int> both_cons;
        for (int con_size : var_1->constraints)
        {
            pcon = & (_constraints[con_size]);
            if (pcon->var_coeff.find(var_idx_2) == pcon->var_coeff.end())
            {
                var_delta = pro_var_delta(var_1, pcon, var_idx_1, _cur_assignment[var_idx_1]);
                con_delta = pcon->value + var_delta;
                state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
                score += (pcon->weight * state);
            }
            else 
            {
                both_cons.insert(con_size);
                var_delta = calculate_cons_descent_two_vars(var_idx_1, var_idx_2, pcon);
                con_delta = pcon->value + var_delta;
                state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
                score += (pcon->weight * state);
                //calculate both score;
            }
        }
        for (int con_size : var_2->constraints)
        {
            pcon = & (_constraints[con_size]);
            if (both_cons.find(con_size) == both_cons.end())
            {
                var_delta = pro_var_delta(var_2, pcon, var_idx_2, _cur_assignment[var_idx_2]);
                con_delta = pcon->value + var_delta;
                state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
                score += (pcon->weight * state);
            }
            else 
            {
                //calculate both score;
            }
        }
        // calculate dscore in obj
        // score += (_object_weight * pro_var_delta_in_obj_cy(bin_var, var_pos, _cur_assignment[var_pos])) / avg_bound;
        // score += (_object_weight * pro_var_delta_in_obj_cy(bin_var, var_pos, _cur_assignment[var_pos]));
        score = 0;
        score -= _object_weight * calculate_obj_descent_two_vars(var_idx_1, var_idx_2);
        return score;
    }

    Float qp_solver::calculate_obj_descent_two_vars(int var_idx_1, int var_idx_2)
    {
        Float coeff_value = 0;
        Float coeff_value_2 = 0;
        int li_var_idx;
        Float li_var_coeff;
        Float change_value_1 = (_cur_assignment[var_idx_1] == 0) ? 1 : -1;
        Float change_value_2 = (_cur_assignment[var_idx_2] == 0) ? 1 : -1;
        var * var_1 = &(_vars[var_idx_1]);
        var * var_2 = &(_vars[var_idx_2]);
        Float both_coeff = 0;
        coeff_value += var_1->obj_constant_coeff;
        coeff_value += var_1->obj_quadratic_coeff;
        coeff_value_2 += var_2->obj_constant_coeff;
        coeff_value_2 += var_2->obj_quadratic_coeff;
        for (int linear_pos = 0; linear_pos < var_1->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = var_1->obj_linear_coeff[linear_pos];
            li_var_coeff = var_1->obj_linear_constant_coeff[linear_pos];
            if (li_var_idx != var_idx_2)
                coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            else
                both_coeff = li_var_coeff;
        }
        coeff_value = change_value_1 * coeff_value;
        for (int linear_pos = 0; linear_pos < var_2->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = var_2->obj_linear_coeff[linear_pos];
            li_var_coeff = var_2->obj_linear_constant_coeff[linear_pos];
            if (li_var_idx != var_idx_1)
                coeff_value_2 += _cur_assignment[li_var_idx] * li_var_coeff;
            else if (both_coeff != li_var_coeff)
                cout << " both error " << both_coeff << " " << li_var_coeff << endl;
        }
        coeff_value_2 = change_value_2 * coeff_value_2;
        if (change_value_1 == 1 && change_value_2 == 1) both_coeff = both_coeff;
        else if (change_value_1 != change_value_2) both_coeff = 0;
        else if (change_value_1 == -1 && change_value_2 == -1) both_coeff = - both_coeff;
        return coeff_value + coeff_value_2 + both_coeff;
    }

    int qp_solver::lift_move()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        int var_idx;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        Float change_value;
        int li_var_idx;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        int op_num;
        Float cur_value;
        Float cur_score;
        Float max_score = INT32_MIN;
        Float max_var_idx;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _obj_vars_in_unbounded_constraint.clear();
        //没加入BMS好像，先试试吧
        for (int var_pos : _vars_in_obj)
        {
            lift_move_op(var_pos, cur_score);
            if (cur_score > max_score)
            {
                max_score = cur_score;
                max_var_idx = var_pos;
            }
        }
        // cout << "max score = " << max_score <<endl;
        if (max_score > 0) return max_var_idx;
        else return -1;
    }

    void qp_solver::lift_move_op(int var_idx_1, Float & score)
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        int var_idx = var_idx_1;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        int li_var_idx;
        Float cur_value;
        Float change_value = (cur_value == 0) ? 1 : -1;
        score = INT32_MIN;
        obj_var = & (_vars[var_idx]);
        cur_value = _cur_assignment[var_idx];
        //execute the best value of objvar
        linear_coeff_value = obj_var->obj_constant_coeff;
        for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = obj_var->obj_linear_coeff[linear_pos];
            li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        linear_coeff_value += obj_var->obj_quadratic_coeff;
        if (linear_coeff_value == 0) return ;
        if (linear_coeff_value > 0 && cur_value == 0) return ;
        if (linear_coeff_value < 0 && cur_value == 1) return ;
        for (int con_pos: obj_var->constraints)
        {
            unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
            a_coeff = &(unbound_con->var_coeff[var_idx]);
            if (!judge_bin_var_feasible(var_idx, a_coeff, unbound_con)) return ;
        }
        // score = (- change_value) * linear_coeff_value;
        if (check_var_shift_bool(var_idx, change_value, false)) score = (- change_value) * linear_coeff_value;//dscore
        
    }

    Float qp_solver::calculate_score_bin_cy(int var_pos, Float change_value)
    {
        //TODO:
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float state;
        var * bin_var;
        Float norm;
        bin_var = & (_vars[var_pos]);
        for (int con_size : bin_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_delta(bin_var, pcon, var_pos, _cur_assignment[var_pos]);
            con_delta = pcon->value + var_delta;
            state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
            norm = fabs(pcon->bound);
            // score += (pcon->weight * state) / norm;
            score += (pcon->weight * state) ;
        }
        // score += (_object_weight * pro_var_delta_in_obj_cy(bin_var, var_pos, _cur_assignment[var_pos])) / avg_bound;
        score += (_object_weight * pro_var_delta_in_obj_cy(bin_var, var_pos, _cur_assignment[var_pos]));
        return score;
    }

    void qp_solver::random_walk_unsat_bin()
    {
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        unordered_set<int> rand_unsat_idx;
        for (int i = 0; i < rand_num; i++) 
        {
            unordered_set<int>::iterator it(_unsat_constraints.begin());
            std::advance(it, rand() % _unsat_constraints.size());
            rand_unsat_idx.insert(*it);
        }
        for (int unsat_pos : rand_unsat_idx)
        {
            unsat_con = & (_constraints[unsat_pos]);
            // delta = unsat_con->bound - unsat_con->value;
            for (auto var_coeff : unsat_con->var_coeff)
            {
                var_idx = var_coeff.first;
                a_coeff = & (var_coeff.second);
                if (_vars[var_idx].is_bin) insert_var_change_value_bin(var_idx, a_coeff, 0, unsat_con, true);
            }
        }
        int var_pos;
        Float change_value, score;
        select_best_operation_bin(var_pos, change_value, score);
        if (score != INT32_MIN) 
        {
#ifdef DEBUG
            cout << " unsat random walk " << endl;
#endif
            execute_critical_move(var_pos, change_value);
        }
        else 
        {
#ifdef DEBUG
            cout << " no op unsat walk " << endl;
#endif
            no_operation_walk_unsat();
        }
    }

    void qp_solver::insert_var_change_value_bin(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag)
    {
        Float change_value = (_cur_assignment[var_idx] == 0) ? 1 : -1;
        Float li_var_coeff;
        Float quar_coeff = a_coeff->obj_quadratic_coeff;
        Float con_coeff = a_coeff->obj_constant_coeff;
        Float linear_coeff_value = con_coeff + quar_coeff;
        int li_var_idx;
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        if (linear_coeff_value == 0) return;
        if (pcon->is_equal)
        {
            //TODO:需不需要两套池子,把约束里的变量单独拿出来，其他的当无约束的，模拟决定用哪种分数哪种操作
            Float delta = linear_coeff_value * change_value;
            if ((delta > 0 && pcon->value < pcon->bound) || (delta < 0 && pcon->value > pcon->bound))
            {
                if (check_var_shift_bool(var_idx, change_value, rand_flag))
                {
                    _operation_vars_sub.push_back(var_idx);
                    _operation_value_sub.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                }
            }
            return;
        }
        bool insert_flag = (linear_coeff_value < 0) ^ (_cur_assignment[var_idx] == 0);
        bool insert_switch = (pcon->is_less) ^ (insert_flag);
        if (insert_switch)
        {
            if (check_var_shift_bool(var_idx, change_value, rand_flag))
            {
                _operation_vars_sub.push_back(var_idx);
                _operation_value_sub.push_back(change_value);
                _operation_cons_pos.push_back(pcon->index);
            }
        }
    }

    void qp_solver::insert_operation_unsat_bin()
    {
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        // 创建按权重从大到小排序的优先队列
        // std::priority_queue<std::pair<int, int>> unsat_queue; // (weight, constraint_pos)
        
        // // 将所有不可满足约束按权重排序
        // for (int unsat_pos : _unsat_constraints)
        // {
        //     if (_constraints[unsat_pos].tabu_step > _steps) continue;
        //     int weight = (_constraints[unsat_pos]).weight;
        //     unsat_queue.push(std::make_pair(weight, unsat_pos));
        // }
        
        // // 按权重从大到小处理约束，最多处理10个
        // int processed_count = 0;
        // while (!unsat_queue.empty() && processed_count < top_cons_num)
        // {
        //     int unsat_pos = unsat_queue.top().second;
        //     unsat_queue.pop();
            
        //     unsat_con = & (_constraints[unsat_pos]);
        //     // delta = unsat_con->bound - unsat_con->value; //想一下这个对不对
        //     for (auto var_coeff : unsat_con->var_coeff)
        //     {
        //         var_idx = var_coeff.first;
        //         a_coeff = & (var_coeff.second);
        //         // insert_var_change_value_bin(var_idx, a_coeff, delta, unsat_con);
        //         insert_var_change_value_bin(var_idx, a_coeff, 0, unsat_con, false);
        //     }
        //     processed_count++;
        // }
        for (int unsat_pos : _unsat_constraints)
        {
            if (_constraints[unsat_pos].tabu_step > _steps) continue;
            unsat_con = & (_constraints[unsat_pos]);
            for (auto var_coeff : unsat_con->var_coeff)
            {
                var_idx = var_coeff.first;
                a_coeff = & (var_coeff.second);
                insert_var_change_value_bin(var_idx, a_coeff, 0, unsat_con, false);
            }
        }
    }

    Float qp_solver::calculate_score_bin(int var_pos, Float change_value)
    {
        //TODO:
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float state;
        var * bin_var;
        bin_var = & (_vars[var_pos]);
        for (int con_size : bin_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_delta(bin_var, pcon, var_pos, _cur_assignment[var_pos]);
            con_delta = pcon->value + var_delta;
            state = judge_cons_state_bin(pcon, var_delta, con_delta);
            score += pcon->weight * state;
        }
        // if (_unsat_constraints.size() == 0) score = 0;
        // score += _object_weight * pro_var_delta_in_obj(bin_var, var_pos, _cur_assignment[var_pos]);
        return score;
    }

    void qp_solver::random_walk_sat_bin()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        var * obj_var;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        int li_var_idx;
        Float best_value;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        int no_operation_var = rand() % _vars.size();
        unordered_set<int> rand_obj_idx;
        bool is_bool;
        int op_num;
        Float cur_value, change_value;
        if (_obj_vars_in_unbounded_constraint.size() == 0)
        {
            // cout << " _obj_vars_in_unbounded_constraint.size() = 0  error " << endl;
            // exit(0);
            no_bound_sat_move();
            return;
        }
        for (int i = 0; i < rand_num_obj; i++) 
        {
            unordered_set<int>::iterator it(_obj_vars_in_unbounded_constraint.begin());
            std::advance(it, rand() % _obj_vars_in_unbounded_constraint.size());
            rand_obj_idx.insert(*it);
            if (i == 0) no_operation_var = *it; 
        }
        for (int var_pos : rand_obj_idx)
        {
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            change_value = (cur_value == 0) ? 1 : -1;
            linear_coeff_value = obj_var->obj_constant_coeff;
            op_num = _operation_vars_sub.size();
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            }
            linear_coeff_value += obj_var->obj_quadratic_coeff;
            if (linear_coeff_value == 0) continue;
            if (linear_coeff_value > 0 && cur_value == 0) continue;
            if (linear_coeff_value < 0 && cur_value == 1) continue;
            for (int con_pos: obj_var->constraints)
            {
                unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                a_coeff = &(unbound_con->var_coeff[var_pos]);
                if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                {
                    insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, true);       
                }
            }
            // op_num = _operation_vars_sub.size() - op_num;
            // if (op_num == 0)
            // {
            //     cout << " randowm: op_num = 0 " << endl;
            //     if ((linear_coeff_value < 0 && cur_value == 0) || (linear_coeff_value > 0 && cur_value == 1))
            //     {
            //         _obj_vars_in_unbounded_constraint.insert(var_pos);
            //         if (check_var_shift_bool(var_pos, change_value, true))
            //         {
            //             _operation_vars_sub.push_back(var_pos);
            //             _operation_value_sub.push_back(change_value);
            //         }
            //     }
            // }
        }
        int var_pos;
        Float change_value_2, score;
        select_best_operation_bin(var_pos, change_value_2, score);
        if (score != INT32_MIN) 
        {
#ifdef DEBUG
            cout << " sat random walk " << endl;
#endif
            execute_critical_move(var_pos, change_value_2);
        }
        else 
        {
#ifdef DEBUG
            cout << " unsat random walk " << endl;
#endif
            Float value = (_cur_assignment[no_operation_var] == 0) ? 1 : -1;
            if (check_var_shift_bool(no_operation_var, value, 1)) execute_critical_move(no_operation_var, value);
        }
    }

    bool qp_solver::insert_var_change_value_sat_bin(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, Float symvalue, bool rand_flag)
    {
        Float change_value = (_cur_assignment[var_idx] == 0) ? 1 : -1;
        Float li_var_coeff;
        Float quar_coeff = a_coeff->obj_quadratic_coeff;
        Float con_coeff = a_coeff->obj_constant_coeff;
        Float linear_coeff_value = con_coeff + quar_coeff;
        int li_var_idx;
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        if (linear_coeff_value == 0) 
        {
            if (check_var_shift_bool(var_idx, change_value, rand_flag))
            {
                _operation_vars_sub.push_back(var_idx);
                _operation_value_sub.push_back(change_value);
                _operation_cons_pos.push_back(pcon->index);
            }
            return true;
        }
        bool insert_flag = (linear_coeff_value < 0) ^ (_cur_assignment[var_idx] == 0);
        // bool insert_switch = (pcon->is_less) ^ (insert_flag);
        bool less = pcon->is_less;
        if (insert_flag)//check
        {
            if (less && (fabs(linear_coeff_value) + pcon->value <= pcon->bound))
            {
                if (check_var_shift_bool(var_idx, change_value, rand_flag))
                {
                    _operation_vars_sub.push_back(var_idx);
                    _operation_value_sub.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                }
                return true;
            }
            else if (!less)
            {
                if (check_var_shift_bool(var_idx, change_value, rand_flag))
                {
                    _operation_vars_sub.push_back(var_idx);
                    _operation_value_sub.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                }
                return true;
            }
            return false;
            //up
            //consider 1.symvalue > 0 < 0, 2.pcon isless, 3. is break the sat state of cons;
        }
        else 
        {
            //down
            if (!less && (pcon->value - fabs(linear_coeff_value)<= pcon->bound))
            {
                if (check_var_shift_bool(var_idx, change_value, rand_flag))
                {
                    _operation_vars_sub.push_back(var_idx);
                    _operation_value_sub.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                }
                return true;
            }
            else if (less)
            {
                if (check_var_shift_bool(var_idx, change_value, rand_flag))
                {
                    _operation_vars_sub.push_back(var_idx);
                    _operation_value_sub.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                }
                return true;
            }
            return false;
        }
        return false;
    }

    void qp_solver::insert_operation_sat_bin()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        int var_idx;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        Float change_value;
        int li_var_idx;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        int op_num;
        Float cur_value;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        _obj_vars_in_unbounded_constraint.clear();
        
        // 预先找出权重最高的10个约束
        // std::priority_queue<std::pair<int, int>> global_constraint_queue; // (weight, constraint_pos)
        // std::unordered_set<int> top_constraints; // 存储权重最高的10个约束位置
        
        // // 收集所有约束的权重
        // for (int var_pos : _vars_in_obj)
        // {
        //     obj_var = & (_vars[var_pos]);
        //     for (int con_pos: obj_var->constraints)
        //     {
        //         if (_constraints[con_pos].tabu_step > _steps) continue;
        //         int weight = (_constraints[con_pos]).weight;
        //         global_constraint_queue.push(std::make_pair(weight, con_pos));
        //     }
        // }
        
        // // 取出权重最高的10个约束
        // int constraint_count = 0;
        // while (!global_constraint_queue.empty() && constraint_count < top_cons_num)
        // {
        //     int con_pos = global_constraint_queue.top().second;
        //     global_constraint_queue.pop();
        //     top_constraints.insert(con_pos);
        //     constraint_count++;
        // }
        
        for (int var_pos : _vars_in_obj)
        {
            op_num = _operation_vars_sub.size();
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            change_value = (cur_value == 0) ? 1 : -1;
            //execute the best value of objvar
            linear_coeff_value = obj_var->obj_constant_coeff;
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            }
            linear_coeff_value += obj_var->obj_quadratic_coeff;
            if (linear_coeff_value == 0) continue;
            if (linear_coeff_value > 0 && cur_value == 0) continue;
            if (linear_coeff_value < 0 && cur_value == 1) continue;
            // 这里再好好想想，是不是要维护可满足性质呢？
            //TODO:采样目标函数，要不太大了，目标函数感觉要用CY学姐的
        
            // 只处理预先选出的权重最高的10个约束
            for (int con_pos: obj_var->constraints)
            {
                if (_constraints[con_pos].tabu_step > _steps) continue;
                // 只处理在top_constraints中的约束
                // if (top_constraints.find(con_pos) == top_constraints.end())
                //     continue;
                    
                /*
                1.不一定非得选unbound
                2.等式没有unbound，怎么插入操作呢此时？还得分一次二次的
                3.插入对称轴等操作
                4.insert 函数里面加入等式情况
                5.变量不在任何约束里出现
                6. _obj_vars_in_unbounded_constraint.insert(var_pos); random walk里也要改
                */
                unbound_con = & (_constraints[con_pos]);
                a_coeff = &(unbound_con->var_coeff[var_pos]);
                if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                {
                    // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                    if (insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false)) //TODO:check
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                    
                }
            }
            //应该留着
            // op_num = _operation_vars_sub.size() - op_num;
            // if (op_num == 0)
            // {
            //     // cout << "op num = 0 " << endl;
            //     cout << " greedy: op_num = 0 " << endl;
            //     if ((linear_coeff_value < 0 && cur_value == 0) || (linear_coeff_value > 0 && cur_value == 1))
            //     {
            //         _obj_vars_in_unbounded_constraint.insert(var_pos);
            //         if (check_var_shift_bool(var_pos, change_value, false))
            //         {
            //             _operation_vars_sub.push_back(var_pos);
            //             _operation_value_sub.push_back(change_value);
            //         }
            //     }
            // }//这里有问题,是unbound没维护好还是insert函数没写好，如果都没问题的话，得重新换选变量机制然后把评分函数得换一换，
        }
    }

    void qp_solver::no_bound_sat_move()
    {
        var * obj_var;
        int var_idx;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        Float change_value;
        int li_var_idx;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        int op_num;
        Float cur_value;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();
        _obj_vars_in_unbounded_constraint.clear();
        for (int var_pos : _vars_in_obj)
        {
            op_num = _operation_vars_sub.size();
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            change_value = (cur_value == 0) ? 1 : -1;
            //execute the best value of objvar
            linear_coeff_value = obj_var->obj_constant_coeff;
            for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
            {
                li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
            }
            linear_coeff_value += obj_var->obj_quadratic_coeff;
            if (linear_coeff_value == 0) continue;
            if (linear_coeff_value > 0 && cur_value == 0) continue;
            if (linear_coeff_value < 0 && cur_value == 1) continue;
            // 这里再好好想想，是不是要维护可满足性质呢？
            //TODO:采样目标函数，要不太大了，目标函数感觉要用CY学姐的
            if (check_var_shift_bool(var_pos, change_value, true))
            {
                _operation_vars_sub.push_back(var_pos);
                _operation_value_sub.push_back(change_value);
                _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
            }
        }
        int var_pos;
        Float change_value_2, score;
        select_best_operation_bin(var_pos, change_value_2, score);
        if (score > INT32_MIN) 
        {
#ifdef DEBUG
            cout << " sat random walk " << endl;
#endif
            execute_critical_move(var_pos, change_value_2);
        }
        else 
        {
#ifdef DEBUG
            cout << " unsat random walk " << endl;
#endif
            vector<int> rand_monos;
            Float obj_delta;
            int mono_pos;
            monomial * mono;
            Float cur_value;
            Float change_value;
            Float value_1, value_2;
            _operation_vars_sub.clear();
            _operation_value_sub.clear();
            _operation_cons_pos.clear();
            for (int rand_times = 0; rand_times < 40; rand_times++)
            {
                mono_pos = rand() % _object_monoials.size();
                mono = & (_object_monoials[mono_pos]);
                obj_delta = pro_mono(*mono);
                if (mono->coeff > 0) 
                {
                    if (obj_delta > 0)
                    {
                        for (int var_pos : mono->m_vars)
                        {
                            cur_value = _cur_assignment[var_pos];
                            change_value = (cur_value == 0) ? 1 : -1;
                            if (check_var_shift_bool(var_pos, change_value, true))
                            {
                                _operation_vars_sub.push_back(var_pos);
                                _operation_value_sub.push_back(change_value);
                                _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                            }
                        }
                    }
                    else if (mono->is_multilinear)//控制x2的空间变大
                    {
                        value_1 = _cur_assignment[mono->m_vars[0]];
                        value_2 = _cur_assignment[mono->m_vars[1]];
                        if (value_1 != value_2)
                        {
                            if (value_1 == 0)
                            {
                                change_value = (value_2 == 0) ? 1 : -1;
                                if (check_var_shift_bool(mono->m_vars[1], change_value, true))
                                {
                                    _operation_vars_sub.push_back(mono->m_vars[1]);
                                    _operation_value_sub.push_back(change_value);
                                    _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                                }
                            }
                            else
                            {
                                change_value = (value_1 == 0) ? 1 : -1;
                                if (check_var_shift_bool(mono->m_vars[0], change_value, true))
                                {
                                    _operation_vars_sub.push_back(mono->m_vars[0]);
                                    _operation_value_sub.push_back(change_value);
                                    _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                                }
                            }
                        }
                    }
                }
                else if (mono->coeff < 0 && obj_delta == 0) 
                {
                    if (!mono->is_multilinear)
                    {
                        for (int var_pos : mono->m_vars)
                        {
                            cur_value = _cur_assignment[var_pos];
                            change_value = (cur_value == 0) ? 1 : -1;
                            if (check_var_shift_bool(var_pos, change_value, true))
                            {
                                _operation_vars_sub.push_back(var_pos);
                                _operation_value_sub.push_back(change_value);
                                _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                            }
                        }
                    }
                    else
                    {
                        value_1 = _cur_assignment[mono->m_vars[0]];
                        value_2 = _cur_assignment[mono->m_vars[1]];
                        if (value_1 != value_2)
                        {
                            if (value_1 == 0)
                            {
                                change_value = (value_1 == 0) ? 1 : -1;
                                if (check_var_shift_bool(mono->m_vars[0], change_value, true))
                                {
                                    _operation_vars_sub.push_back(mono->m_vars[0]);
                                    _operation_value_sub.push_back(change_value);
                                    _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                                }
                            }
                            else
                            {
                                change_value = (value_2 == 0) ? 1 : -1;
                                if (check_var_shift_bool(mono->m_vars[1], change_value, true))
                                {
                                    _operation_vars_sub.push_back(mono->m_vars[1]);
                                    _operation_value_sub.push_back(change_value);
                                    _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                                }
                            }
                        }
                        else 
                        {
                            for (int var_pos : mono->m_vars)
                            {
                                cur_value = _cur_assignment[var_pos];
                                change_value = (cur_value == 0) ? 1 : -1;
                                if (check_var_shift_bool(var_pos, change_value, true))
                                {
                                    _operation_vars_sub.push_back(var_pos);
                                    _operation_value_sub.push_back(change_value);
                                    _operation_cons_pos.push_back(-1); // 没有约束关联，使用-1
                                }
                            }
                        }
                    }
                }
            }
            int var_pos;
            Float change_value_2, score;
            select_best_operation_bin(var_pos, change_value_2, score);
            if (0) execute_critical_move(var_pos, change_value_2);
            else 
            {
                int rand_idx = rand() % _vars.size();
                // if (_cur_assignment[rand_idx] == 0) execute_critical_move_no_cons(rand_idx,1);
                // else execute_critical_move_no_cons(rand_idx,-1);
                Float value = (_cur_assignment[rand_idx] == 0) ? 1 : -1;
                if (check_var_shift_bool(rand_idx, value, 1)) execute_critical_move(rand_idx, value);
            }
        }
    }

    void qp_solver::select_best_operation_bin(int & var_pos, Float & change_value, Float & score)
    {
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars_sub.size();
        // 确保数组大小一致
        if (op_size != _operation_cons_pos.size())
        {
            cout << "error" << endl;
            exit(0);
            return;
        }
        bool is_bms;
        if (op_size <= bms) 
        {
            cnt = op_size;
            is_bms = false;
        } 
        else 
        {
            cnt = bms;
            is_bms = true;
        }
        int cur_var;
        Float cur_shift, cur_score;
        int rand_index, cons_pos = -1, cur_cons_pos;
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars_sub[rand_index];
                cur_shift = _operation_value_sub[rand_index];
                cur_cons_pos = _operation_cons_pos[rand_index];
                _operation_vars_sub[rand_index] = _operation_vars_sub[op_size - i - 1];
                _operation_value_sub[rand_index] = _operation_value_sub[op_size - i - 1];
                _operation_cons_pos[rand_index] = _operation_cons_pos[op_size - i - 1];
            } 
            else {
                cur_var = _operation_vars_sub[i];
                cur_shift = _operation_value_sub[i];
                cur_cons_pos = _operation_cons_pos[i];
            }
            if (is_cur_feasible)
                cur_score = calculate_score_bin_cy(cur_var, cur_shift);
            else 
            {
                if (cons_num_type == 0)
                    cur_score = calculate_score_bin_cy(cur_var, cur_shift);
                else 
                    cur_score = calculate_score_bin(cur_var, cur_shift);
            }
            if (cur_score > score) {
                score = cur_score;
                var_pos = cur_var;
                change_value = cur_shift;
                cons_pos = cur_cons_pos;
            }
        }
        if (_constraint_tabu_enabled && cons_pos != -1)
        {
            _constraints[cons_pos].tabu_step = _steps + rand() % 10 + 3;
        }
    }

    void qp_solver::local_search_bin()
    {
        std::srand(seed_num);
        initialize();
        // exit(0);
        int var_pos;
        int lift_var;
        Float change_value, score;
        for (_steps = 0; _steps <= _max_steps; _steps++)
        {
            //TODO
#ifdef DEBUG
            cout << " unsat num: "  << _unsat_constraints.size()  << endl;
#endif
            if (_steps % 1000 == 0 && (TimeElapsed() > _cut_off)) break;
            if (is_cur_feasible)
            {
                // lift_var = lift_move();
                // if (lift_var != -1) 
                // {
                //     // cout << "lift move" << endl;
                //     execute_critical_move(lift_var, 1 - _cur_assignment[lift_var]);
                //     continue;
                // }
                insert_operation_sat_bin();
                select_best_operation_bin(var_pos, change_value, score);
                if (score > 0) 
                {
#ifdef DEBUG
                    cout << " sat greedy walk " << endl;
#endif
                    execute_critical_move(var_pos, change_value);
                }
                else 
                {
                    update_weight();
                    random_walk_sat_bin();
                }
            }
            else 
            {
                insert_operation_unsat_bin();
                select_best_operation_bin(var_pos, change_value, score);
                if (score > 0) 
                {
#ifdef DEBUG
                cout << " unsat greedy walk " << endl;
#endif
                    execute_critical_move(var_pos, change_value);
                }
                else 
                {
                    update_weight();
                    random_walk_unsat_bin();
                }
            }
        }
        if (_best_object_value == INT32_MAX) cout << INT32_MAX << endl;
        else
        {
            if (is_minimize)
                cout << std::fixed << " best obj min= " ;
            else 
                cout << std::fixed << " best obj max= " ;
            if (is_minimize) cout << _best_object_value + _obj_constant;
            else cout << -_best_object_value + _obj_constant;
            // cout << endl << " solution : " <<endl;
            // print_best_solution();
        } 
    }

}