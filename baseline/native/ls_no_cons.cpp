#include "sol.h"
namespace solver
{

    bool qp_solver::fps_move()
    {
        return false;
        unordered_set<int> first_vars;
        vector<int> rand_monos;
        Float obj_delta;
        int mono_pos;
        monomial * mono;
        Float cur_value;
        Float change_value;
        Float value_1, value_2;
        Float change_value_fps_1, change_value_fps_2, score_fps_1, score_fps_2, best_score_fps = INT32_MIN;
        int best_var_1, best_var_2, s_var;
        for (int rand_times = 0; rand_times < 40; rand_times++) //40
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
                            first_vars.insert(var_pos);
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
                                first_vars.insert(mono->m_vars[1]);
                            }
                        }
                        else
                        {
                            change_value = (value_1 == 0) ? 1 : -1;
                            if (check_var_shift_bool(mono->m_vars[0], change_value, true))
                            {
                                first_vars.insert(mono->m_vars[0]);
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
                            first_vars.insert(var_pos);
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
                                first_vars.insert(mono->m_vars[0]);
                            }
                        }
                        else
                        {
                            change_value = (value_2 == 0) ? 1 : -1;
                            if (check_var_shift_bool(mono->m_vars[1], change_value, true))
                            {
                                first_vars.insert(mono->m_vars[1]);
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
                                first_vars.insert(var_pos);
                            }
                        }
                    }
                }
            }
        }
        for (auto f_var : first_vars)
        {
            change_value_fps_1 = (_cur_assignment[f_var] == 0) ? 1 : -1;
            score_fps_1 = calculate_score_no_cons(f_var, change_value_fps_1);
            _cur_assignment[f_var] += change_value_fps_1;
            insert_operation_no_cons();
            select_best_operation_no_cons(s_var, change_value_fps_2, score_fps_2);
            if (score_fps_2 > 0 && score_fps_1 + score_fps_2 > 0)
            {
                // best_score_fps = score_fps_1 + score_fps_2;
                best_var_1 = f_var;
                best_var_2 = s_var;
                _cur_assignment[f_var] -= change_value_fps_1;
                Float best_change_value_1 = (_cur_assignment[best_var_1] == 0) ? 1 : -1;
                Float best_change_value_2 = (_cur_assignment[best_var_2] == 0) ? 1 : -1;
                execute_critical_move_no_cons(best_var_1, best_change_value_1);
                execute_critical_move_no_cons(best_var_2, best_change_value_2);
                return true;
            }
            _cur_assignment[f_var] -= change_value_fps_1;
        }
        return false;
        if (best_score_fps > 0)
        {
            // cout << "2 flip " << best_var_1 << "   " << best_var_2 << endl; 
            // cout << best_score_fps << endl;
            Float best_change_value_1 = (_cur_assignment[best_var_1] == 0) ? 1 : -1;
            Float best_change_value_2 = (_cur_assignment[best_var_2] == 0) ? 1 : -1;
            execute_critical_move_no_cons(best_var_1, best_change_value_1);
            execute_critical_move_no_cons(best_var_2, best_change_value_2);
            return true;
        }
        return false;
    }

    Float qp_solver::calculate_coeff_in_obj(int var_pos)
    {
        var * obj_var = & (_vars[var_pos]);
        Float linear_coeff_value = obj_var->obj_constant_coeff;
        Float li_var_coeff;
        int li_var_idx;
        for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = obj_var->obj_linear_coeff[linear_pos];
            li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        linear_coeff_value += obj_var->obj_quadratic_coeff;
        return linear_coeff_value;
    }

    bool qp_solver::two_flip_no_cons()
    {
        return false;
        unordered_set<int> rand_monos;
        Float obj_delta;
        int mono_pos;
        monomial * mono;
        Float cur_value;
        Float change_value_1, change_value_2;
        int var_1, var_2;
        Float value_1, value_2;
        Float cur_delta_1, cur_delta_2;
        Float best_var_1, best_var_2;
        Float best_descent = INT32_MAX;
        Float delta_mono;
        for (int rand_times = 0; rand_times < 40; rand_times++)
        {
            mono_pos = rand() % _object_monoials.size();
            if (rand_monos.find(mono_pos) == rand_monos.end()) rand_monos.insert(mono_pos);
            else continue;
            mono = & (_object_monoials[mono_pos]);
            if (mono->m_vars.size() == 2)
            {
                var_1 = mono->m_vars[0];
                var_2 = mono->m_vars[1];
                value_1 = _cur_assignment[var_1];
                value_2 = _cur_assignment[var_2];
                change_value_1 = (value_1 == 0) ? 1 : -1;
                change_value_2 = (value_2 == 0) ? 1 : -1;
                if (value_1 == value_2) delta_mono = mono->coeff;
                else delta_mono = - mono->coeff;
                if (!check_var_shift_bool(var_1, change_value_1, false)) continue;
                if (!check_var_shift_bool(var_2, change_value_2, false)) continue;
                if (_cur_delta[var_1] == INT32_MIN) //这里不能是-1
                {
                    cur_delta_1 = calculate_coeff_in_obj(var_1) * (change_value_1);
                    _cur_delta[var_1] = cur_delta_1;
                }
                else cur_delta_1 = _cur_delta[var_1];
                if (_cur_delta[var_2] == INT32_MIN)
                {
                    cur_delta_2 = calculate_coeff_in_obj(var_2) * (change_value_2);
                    _cur_delta[var_2] = cur_delta_2;
                }
                else cur_delta_2 = _cur_delta[var_2];
                // if (_cur_delta[var_1] < 0)
                // {
                //     Float best_change_value_1 = (_cur_assignment[var_1] == 0) ? 1 : -1;
                //     execute_critical_move_no_cons(var_1, best_change_value_1);
                //     return true;
                // }
                // else if (_cur_delta[var_2] < 0)
                // {
                //     Float best_change_value_2 = (_cur_assignment[var_2] == 0) ? 1 : -1;
                //     execute_critical_move_no_cons(var_2, best_change_value_2);
                //     return true;
                // }
                cur_value = delta_mono + cur_delta_1 + cur_delta_2;
                if (cur_value < best_descent && cur_value < cur_delta_1 && cur_value < cur_delta_2)
                {//这里再改改i
                    best_descent = delta_mono + cur_delta_1 + cur_delta_2;
                    best_var_1 = var_1;
                    best_var_2 = var_2;
                } 
            }
        }
        // cout << best_descent << endl;
        if (best_descent <= -1)
        {
            // cout << "2 flip " << best_var_1 << "   " << best_var_2 << endl; 
            // cout << best_descent << endl;
            Float best_change_value_1 = (_cur_assignment[best_var_1] == 0) ? 1 : -1;
            Float best_change_value_2 = (_cur_assignment[best_var_2] == 0) ? 1 : -1;
            execute_critical_move_no_cons(best_var_1, best_change_value_1);
            execute_critical_move_no_cons(best_var_2, best_change_value_2);
            return true;
        }
        else return false;
    }

    void qp_solver::random_walk_no_cons()
    {
        vector<int> rand_monos;
        Float obj_delta;
        int mono_pos;
        monomial * mono;
        Float cur_value;
        Float change_value;
        Float value_1, value_2;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        for (int rand_times = 0; rand_times < 40; rand_times++) //40
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
                            }
                        }
                        else
                        {
                            change_value = (value_1 == 0) ? 1 : -1;
                            if (check_var_shift_bool(mono->m_vars[0], change_value, true))
                            {
                                _operation_vars_sub.push_back(mono->m_vars[0]);
                                _operation_value_sub.push_back(change_value);
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
                            }
                        }
                        else
                        {
                            change_value = (value_2 == 0) ? 1 : -1;
                            if (check_var_shift_bool(mono->m_vars[1], change_value, true))
                            {
                                _operation_vars_sub.push_back(mono->m_vars[1]);
                                _operation_value_sub.push_back(change_value);
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
                            }
                        }
                    }
                }
            }
        }
        int var_pos;
        Float change_value_2, score;
        select_best_operation_no_cons(var_pos, change_value_2, score);
        // cout << score << endl;
        if (score != INT32_MIN) execute_critical_move_no_cons(var_pos, change_value_2);
        else 
        {
            int rand_idx = rand() % _vars.size();
            // if (_cur_assignment[rand_idx] == 0) execute_critical_move_no_cons(rand_idx,1);
            // else execute_critical_move_no_cons(rand_idx,-1);
            Float value = (_cur_assignment[rand_idx] == 0) ? 1 : -1;
            if (check_var_shift_bool(rand_idx, value, 1)) execute_critical_move_no_cons(rand_idx, value);
        }
    }

    void qp_solver::update_weight_no_cons()
    {
        // Float obj_delta;
        // for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
        // {
        //     obj_delta = pro_mono(_object_monoials[mono_pos]);
        //     if (_object_monoials[mono_pos].coeff > 0 && obj_delta > 0 && _object_weights[mono_pos] < 10) 
        //     {
        //         if (_object_monoials[mono_pos].m_vars.size() == 1) _object_weights[mono_pos]++;
        //         else if (_cur_assignment[_object_monoials[mono_pos].m_vars[0]] == 1 && _cur_assignment[_object_monoials[mono_pos].m_vars[1]] == 1)
        //             _object_weights[mono_pos]++;
        //     }
        //     else if (_object_monoials[mono_pos].coeff < 0 && obj_delta == 0 && _object_weights[mono_pos] < 10) 
        //     {
        //         if (_object_monoials[mono_pos].m_vars.size() == 1) _object_weights[mono_pos]++;
        //         else if (_cur_assignment[_object_monoials[mono_pos].m_vars[0]] == 0 && _cur_assignment[_object_monoials[mono_pos].m_vars[1]] == 0)
        //             _object_weights[mono_pos]++;
        //     }
        // }
    }

    Float qp_solver::calculate_score_no_cons(int var_pos, Float change_value)
    {
        //TODO:
        Float score = 0;
        for (int mono_pos : _vars[var_pos].obj_monomials)
        {
            score -= pro_mono_inc(_object_monoials[mono_pos], var_pos) * _object_weights[mono_pos];
        }
        return score;
    }

    void qp_solver::execute_critical_move_no_cons(int var_pos, Float change_value)
    {
        // change the value of cons, sat state
        // change the is_cur_feasible
        // change the tabu of var
        // change the cur_value
        var * nor_var;
        _cur_assignment[var_pos] += change_value;
        nor_var = & (_vars[var_pos]);
        if (change_value < 0) _vars[var_pos].last_pos_step = _steps + 3 + rand() % 10;
        else _vars[var_pos].last_neg_step = _steps + 3 + rand() % 10;
        update_best_solution();
    }

    void qp_solver::insert_operation_no_cons()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        int li_var_idx;
        Float cur_value;
        Float change_value;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        for (int i = 0; i < _vars.size(); i++)
        {
            _cur_delta[i] = INT32_MIN;//这里也有问题
        }
        for (int var_pos : _vars_in_obj)
        {
            // if (rand() % 10000 < 5000) continue;
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
            if ((linear_coeff_value < 0 && cur_value == 0) || (linear_coeff_value > 0 && cur_value == 1))
            {
                if (check_var_shift_bool(var_pos, change_value, false))
                {
                    _operation_vars_sub.push_back(var_pos);
                    _operation_value_sub.push_back(change_value);
                }
            }
        }
    }

    void qp_solver::select_best_operation_no_cons(int & var_pos, Float & change_value, Float & score)
    {
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars_sub.size();
        bool is_bms;
        bms = 200;
        if (op_size <= bms) //200
        {
            cnt = op_size;
            is_bms = false;
        } 
        else 
        {
            cnt = bms;
            is_bms = true;
        }
        int cur_var, best_var;
        Float cur_shift, cur_score;
        int rand_index;
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars_sub[rand_index];
                cur_shift = _operation_value_sub[rand_index];
                _operation_vars_sub[rand_index] = _operation_vars_sub[op_size - i - 1];
                _operation_value_sub[rand_index] = _operation_value_sub[op_size - i - 1];
            } 
            else {
                cur_var = _operation_vars_sub[i];
                cur_shift = _operation_value_sub[i];
            }
            cur_score = calculate_score_no_cons(cur_var, cur_shift);
            _cur_delta[cur_var] = - cur_score;
            if (cur_score > score) {
                score = cur_score;
                var_pos = cur_var;
                best_var = cur_var;
                change_value = cur_shift;
            }
            else if (cur_score == score)
            {
                int cur_age = std::max(_vars[cur_var].last_pos_step, _vars[cur_var].last_neg_step);
                int best_age = std::max(_vars[best_var].last_pos_step, _vars[best_var].last_neg_step);
                if (cur_age < best_age)
                {
                    score = cur_score;
                    var_pos = cur_var;
                    best_var = cur_var;
                    change_value = cur_shift;
                }
            }
        }
    }

    void qp_solver::initialize_without_cons()
    {
        polynomial_constraint * pcon;
        Float mono_delta = 0, obj_delta = _obj_constant;
        var * bin_var;
        // int var_pos;
        Float con_delta;
        Float var_delta;
        int score = 0;
        int state;
        int coeff_postive;
        bool is_pos;
        int cur_score;
        _var_num = _vars.size();
        _bool_var_num = _bool_vars.size();
        _int_var_num = _int_vars.size();
        //构建LS的信息,类里其它信息的构建,初始值的给出,约束的满足和不满足,初始化二进制变量的score:
        if (problem_type != 0)
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].is_bin) _cur_assignment.push_back(0);
                else if (_vars[i].has_lower) 
                {  
                    if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(ceil(_vars[i].lower));
                    _cur_assignment.push_back(_vars[i].lower);
                }
                else if (_vars[i].has_upper)
                {
                    if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(floor(_vars[i].lower));
                    _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(1);
            }
        }
        else 
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].is_bin) _cur_assignment.push_back(0);
                else if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) _cur_assignment.push_back(floor(_vars[i].lower));
                else _cur_assignment.push_back(1);
            }
        }
        is_feasible = true;
        is_cur_feasible = true;
        //TODO:上下界初始化
        _object_weight = 1;
        _best_assignment = _cur_assignment;
        for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
        {
            // cout << pro_mono(_object_monoials[mono_pos]) <<endl;
            obj_delta += pro_mono(_object_monoials[mono_pos]);
            // cout <<" cur obj = "<< obj_delta <<endl;
            _object_weights.push_back(1);
        }
        _best_object_value = obj_delta;
            mbd_emit();
        // cout <<" init value: "<< _best_object_value << endl;
        for (int i = 0; i < _vars.size(); i++)
        {
            _cur_delta.push_back(INT32_MIN);//这里也有问题
        }
        // for (int var_pos : _bool_vars)
        // {
        //     // var_pos = _bool_vars[bin_size];
        //     bin_var = & (_vars[var_pos]);
        //     score = 0;
        //     is_pos = (_cur_assignment[var_pos] > 0);
        //     coeff_postive = pro_var_delta_in_obj(bin_var, var_pos, is_pos);
        //     score += _object_weight * coeff_postive;
        //     bin_var->obj_score = _object_weight * coeff_postive;
        //     bin_var->bool_score = score;
        // }
    }

    void qp_solver::local_search_without_cons()
    {
        // std::srand(seed_num);
        std::srand(seed_num);//146 for selby02
        cout << " ls_no_cons " << endl; 
        initialize_without_cons();
        int var_pos;
        Float change_value, score;
        for (_steps = 0; _steps <= _max_steps; _steps++)
        {
            //TODO
            if (_steps % 1000 == 0 && (TimeElapsed() > _cut_off)) break;
            insert_operation_no_cons();//待采样，好像BMS就是采样了，除非增量式
            select_best_operation_no_cons(var_pos, change_value, score);
            //下面的都得改
            if (score > 0) execute_critical_move_no_cons(var_pos, change_value);
            else if (!fps_move())
            {
                update_weight_no_cons();
                random_walk_no_cons();
            }
        }
        if (_best_object_value == INT32_MAX) 
        {
            cout << "process no cons with obj = max error" << endl;
        }
        else
        {
            if (is_minimize)
                cout << std::fixed << " best obj min= " ;
            else 
                cout << std::fixed << " best obj max= " ;
            if (is_minimize) cout << _best_object_value + _obj_constant;
            else cout << -_best_object_value + _obj_constant;
            // cout << endl << " solution : " << endl;
            // print_best_solution();
        } 
    }

}