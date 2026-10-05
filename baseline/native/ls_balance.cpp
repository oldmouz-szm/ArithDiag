#include "sol.h"
namespace solver
{
    
    // 约束tabu相关函数实现
    void qp_solver::set_constraint_tabu_enabled(bool enabled)
    {
        _constraint_tabu_enabled = enabled;
    }

    bool qp_solver::is_constraint_tabu(int constraint_idx)
    {
        if (!_constraint_tabu_enabled) return false;
        return _constraints[constraint_idx].tabu_step > _steps;
    }
    
    void qp_solver::execute_critical_move_mix_more(int var_pos, Float change_value)
    {
        execute_critical_move_mix(var_pos, change_value);
        // Float cur_value = _cur_assignment[var_pos];
        // Float change_value_another;
        // int change_var;
        // for (auto other_inf : _vars[var_pos].equal_pair)
        // {
        //     change_var = other_inf.real_index;
        //     if (!other_inf.has_bool)
        //         change_value_another = cur_value * other_inf.real_coeff + other_inf.constant;
        //     else 
        //         change_value_another = cur_value * other_inf.real_coeff + other_inf.constant + _cur_assignment[other_inf.bool_index] * other_inf.bool_coeff;
        //     change_value_another -= _cur_assignment[change_var];
        //     // cout << _vars[change_var].name << " " << change_value_another << endl;
        //     if (check_var_shift(change_var, change_value_another, true))
        //     {
        //         // cout << change_var << " " << change_value_another << endl;
        //         execute_critical_move_mix(change_var, change_value_another);
        //     }
        // }
    }

    void qp_solver::select_best_operation_with_pair_mix(int & var_idx_1, Float & change_value_1, int & var_idx_2, Float & change_value_2, Float & score)
    {
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars_pair.size();
        // 仅在开启tabu时检查并使用_cons_pos
        if (_constraint_tabu_enabled)
        {
            // 检查 _operation_vars_pair.size() 和 _operation_cons_pos 中对应 _operation_vars_pair 的条目数量
            // 由于 _operation_cons_pos 包含对应 _operation_vars 的条目（值为 -1）和对应 _operation_vars_pair 的条目（值为约束索引），
            // 我们需要确保只检查对应 _operation_vars_pair 的条目
        {
            int cons_pos_size = 0;
            for (int i = 0; i < _operation_cons_pos.size(); i++)
            {
                if (_operation_cons_pos[i] != -1) // -1 表示对应 _operation_vars 的条目
                {
                    cons_pos_size++;
                }
            }
            // if (op_size != cons_pos_size)
            // {
            //     // 只在最后输出一次错误信息
            //     static bool error_reported = false;
            //     if (!error_reported) {
            //         cout << "Error: _operation_vars_pair.size() = " << op_size 
            //              << " != _operation_cons_pos.size() (excluding -1) = " << cons_pos_size << endl;
            //         error_reported = true;
            //     }
            //     return;
            // }
        }
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
        int cur_var, cur_var_2;
        Float cur_shift, cur_shift_2, cur_score;
        int rand_index, cons_pos = -1, cur_cons_pos = -1;
        
        // 创建 _operation_cons_pos 中对应 _operation_vars_pair 的索引映射
        vector<int> pair_cons_indices;
        if (_constraint_tabu_enabled)
        {
            // 计算 _operation_cons_pos 中对应 _operation_vars_pair 的条目数量
            int cons_pos_size = 0;
            for (int i = 0; i < _operation_cons_pos.size(); i++)
            {
                if (_operation_cons_pos[i] != -1) // -1 表示对应 _operation_vars 的条目
                {
                    cons_pos_size++;
                    pair_cons_indices.push_back(i);
                }
            }
            // 如果 _operation_vars_pair 为空，但 _operation_cons_pos 中有非 -1 的条目，
            // 说明有其他地方添加了 _operation_cons_pos 但没有添加对应的 _operation_vars_pair
            // if (op_size == 0 && cons_pos_size > 0)
            // {
            //     // 只在最后输出一次错误信息
            //     static bool error_reported = false;
            //     if (!error_reported) {
            //         cout << "Error: _operation_vars_pair.size() = " << op_size 
            //              << " != _operation_cons_pos.size() (excluding -1) = " << cons_pos_size << endl;
            //         error_reported = true;
            //     }
            //     return;
            // }
        }
        
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars_pair[rand_index].var_1;
                cur_var_2 = _operation_vars_pair[rand_index].var_2;
                cur_shift = _operation_vars_pair[rand_index].value_1;
                cur_shift_2 = _operation_vars_pair[rand_index].value_2;
                if (_constraint_tabu_enabled && rand_index < pair_cons_indices.size()) 
                    cur_cons_pos = _operation_cons_pos[pair_cons_indices[rand_index]];
                _operation_vars_pair[rand_index] = _operation_vars_pair[op_size - i - 1];
                if (_constraint_tabu_enabled && rand_index < pair_cons_indices.size() && (op_size - i - 1) < pair_cons_indices.size())
                    _operation_cons_pos[pair_cons_indices[rand_index]] = _operation_cons_pos[pair_cons_indices[op_size - i - 1]];
            } 
            else 
            {
                cur_var = _operation_vars_pair[i].var_1;
                cur_var_2 = _operation_vars_pair[i].var_2;
                cur_shift = _operation_vars_pair[i].value_1;
                cur_shift_2 = _operation_vars_pair[i].value_2;
                if (_constraint_tabu_enabled && i < pair_cons_indices.size()) 
                    cur_cons_pos = _operation_cons_pos[pair_cons_indices[i]];
            }
            if (is_cur_feasible)
                cur_score = calculate_score_compensate_cons_mix(cur_var, cur_shift, cur_var_2, cur_shift_2, true);
            else 
                cur_score = calculate_score_compensate_cons_mix(cur_var, cur_shift, cur_var_2, cur_shift_2, false);
            // cout << _vars[cur_var].name << " " << cur_shift << " " << _vars[cur_var_2].name << " " << cur_shift_2 << " " << cur_score << endl;
            // if (is_cur_feasible)
            //     cur_score = calculate_score_compensate_cons(cur_var, cur_var_2);
            // else 
            // {
            //     cout << " not unsat but sat pair selection" << endl;
            //     exit(0);
            // }
            if (cur_score > score) {
                score = cur_score;
                var_idx_1 = cur_var;
                var_idx_2 = cur_var_2;
                change_value_1 = cur_shift;
                change_value_2 = cur_shift_2;
                cons_pos = cur_cons_pos;
            }
        }
        if (cons_pos != -1 && _constraint_tabu_enabled)
        {
            _constraints[cons_pos].tabu_step = _steps + rand() % 10 + 3;
        }
    }

    Float qp_solver::calculate_obj_descent_two_vars_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2)
    {
        Float coeff_value = 0;
        Float coeff_value_2 = 0;
        int li_var_idx;
        Float li_var_coeff;
        var * var_1 = &(_vars[var_idx_1]);
        var * var_2 = &(_vars[var_idx_2]);
        Float both_coeff = 0;
        Float delta = 0;
        Float new_value_1 = _cur_assignment[var_idx_1] + change_value_1;
        Float new_value_2 = _cur_assignment[var_idx_2] + change_value_2;
        if (var_1->obj_quadratic_coeff != 0) delta +=  var_1->obj_quadratic_coeff * ((new_value_1 * new_value_1) - (_cur_assignment[var_idx_1] * _cur_assignment[var_idx_1]));
        if (var_2->obj_quadratic_coeff != 0) delta +=  var_2->obj_quadratic_coeff * ((new_value_2 * new_value_2) - (_cur_assignment[var_idx_2] * _cur_assignment[var_idx_2]));
        coeff_value += var_1->obj_constant_coeff;
        coeff_value_2 += var_2->obj_constant_coeff;
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
        // if (change_value_1 == 1 && change_value_2 == 1) both_coeff = both_coeff;
        // else if (change_value_1 != change_value_2) both_coeff = 0;
        // else if (change_value_1 == -1 && change_value_2 == -1) both_coeff = - both_coeff;
        both_coeff = both_coeff * ((new_value_2 * new_value_1) - (_cur_assignment[var_idx_1] * _cur_assignment[var_idx_2]));
        return coeff_value + coeff_value_2 + both_coeff + delta;
    }

    Float qp_solver::calculate_cons_descent_two_vars_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2, polynomial_constraint * pcon)
    {
        var * var_1 = &(_vars[var_idx_1]);
        var * var_2 = &(_vars[var_idx_2]);
        all_coeff * coeff_1 = &(pcon->var_coeff[var_idx_1]); 
        all_coeff * coeff_2 = &(pcon->var_coeff[var_idx_2]);
        int li_var_idx;
        Float delta = 0;
        Float new_value_1 = _cur_assignment[var_idx_1] + change_value_1;
        Float new_value_2 = _cur_assignment[var_idx_2] + change_value_2;
        if (coeff_1->obj_quadratic_coeff != 0) delta += coeff_1->obj_quadratic_coeff * ((new_value_1 * new_value_1) - (_cur_assignment[var_idx_1] * _cur_assignment[var_idx_1]));
        if (coeff_2->obj_quadratic_coeff != 0) delta += coeff_2->obj_quadratic_coeff * ((new_value_2 * new_value_2) - (_cur_assignment[var_idx_2] * _cur_assignment[var_idx_2]));
        Float linear_coeff_value_1 = coeff_1->obj_constant_coeff;
        Float linear_coeff_value_2 = coeff_2->obj_constant_coeff;
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
        // if (change_value_1 == 1 && change_value_2 == 1) both_coeff = both_coeff;
        // else if (change_value_1 != change_value_2) both_coeff = 0;
        // else if (change_value_1 == -1 && change_value_2 == -1) both_coeff = - both_coeff;
        both_coeff = both_coeff * ((new_value_2 * new_value_1) - (_cur_assignment[var_idx_1] * _cur_assignment[var_idx_2]));
        return linear_coeff_value_1 + linear_coeff_value_2 + both_coeff + delta;
    }

    Float qp_solver::calculate_score_compensate_cons_mix(int var_idx_1, Float change_value_1, int var_idx_2, Float change_value_2, bool is_distance)
    {
        Float score = 0;
        // score -= _object_weight * calculate_obj_descent_two_vars(var_idx_1, var_idx_2);
        // return score;
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
                pcon = & (_constraints[con_size]);
                if (!var_1->is_bin)
                {
                    var_delta = pro_var_value_delta(var_1, pcon, var_idx_1, _cur_assignment[var_idx_1], _cur_assignment[var_idx_1] + change_value_1);
                    con_delta = pcon->value + var_delta;
                    if (is_distance) state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);
                    else state = judge_cons_state_mix(pcon, var_delta, con_delta);
                }
                // score += pcon->weight * state;
                else
                {
                    var_delta = pro_var_delta(var_1, pcon, var_idx_1, _cur_assignment[var_idx_1]);
                    con_delta = pcon->value + var_delta;
                    if (is_distance) state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
                    else state = judge_cons_state_mix(pcon, var_delta, con_delta);
                }
                score += pcon->weight * state;
            }
            else 
            {
                both_cons.insert(con_size);
                var_delta = calculate_cons_descent_two_vars_mix(var_idx_1, change_value_1, var_idx_2, change_value_2, pcon);
                con_delta = pcon->value + var_delta;
                // state = judge_cons_state_bin_cy(pcon, var_delta, con_delta);
                // state = judge_cons_state_mix(pcon, var_delta, con_delta);
                if (is_distance) state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);
                else state = judge_cons_state_mix(pcon, var_delta, con_delta);
                score += (pcon->weight * state);
                //calculate both score;
            }
        }
        for (int con_size : var_2->constraints)
        {
            pcon = & (_constraints[con_size]);
            if (both_cons.find(con_size) == both_cons.end())
            {
                if (!var_2->is_bin)
                {
                    var_delta = pro_var_value_delta(var_2, pcon, var_idx_2, _cur_assignment[var_idx_2], _cur_assignment[var_idx_2] + change_value_2);
                    con_delta = pcon->value + var_delta;
                    if (is_distance) state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);
                    else state = judge_cons_state_mix(pcon, var_delta, con_delta);
                }
                else 
                {
                    var_delta = pro_var_delta(var_2, pcon, var_idx_2, _cur_assignment[var_idx_2]);
                    con_delta = pcon->value + var_delta;
                    if (is_distance) state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);
                    else state = judge_cons_state_mix(pcon, var_delta, con_delta);
                }
                score += (pcon->weight * state);
            }
            else 
            {
                //calculate both score;
            }
        }
        if (is_distance) score -= _object_weight * calculate_obj_descent_two_vars_mix(var_idx_1, change_value_1, var_idx_2, change_value_2);
        else 
        {
            Float add_reduce_value = calculate_obj_descent_two_vars_mix(var_idx_1, change_value_1, var_idx_2, change_value_2);
            int add_or_reduce;
            if (add_reduce_value == 0) add_or_reduce = 0;
            if (add_reduce_value < 0) add_or_reduce = -1;
            else add_or_reduce = 1;
            score -= _object_weight * add_or_reduce;
        }
        return score;
    }

    void qp_solver::insert_var_change_value_comp_bin(int var_pos, Float change_value_1, int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag)
    {
        Float change_value_bin = (_cur_assignment[var_idx] == 0) ? 1 : -1;
        _cur_assignment[var_idx] += change_value_bin;
        // _cur_assignment[var_pos] += change_value_1; 
        Float mono_delta = 0;
        bool is_post_sat;
        Float bound = pcon->bound;
        for (int mono_pos = 0; mono_pos < pcon->monomials.size(); mono_pos++)
        {
            mono_delta += pro_mono(pcon->monomials[mono_pos]);
        }
        if (pcon->is_equal) is_post_sat = (mono_delta >= bound - eb && mono_delta <= bound + eb);
        else if (pcon->is_less) is_post_sat = (mono_delta <= bound + eb);
        else is_post_sat = (mono_delta >= bound - eb);
        if (is_post_sat)
        {
            if (check_var_shift_bool(var_idx, change_value_bin, rand_flag))
            {
                pair_vars cur(var_pos, var_idx, change_value_1, change_value_bin);
                _operation_vars_pair.push_back(cur);
                _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
            }
        }
        _cur_assignment[var_idx] -= change_value_bin;
        // _cur_assignment[var_pos] -= change_value_1; 
    }

    void qp_solver::insert_var_change_value_comp(int var_pos, Float change_value_1, int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag)
    {
        Float change_value;
        Float li_var_coeff;
        Float quar_coeff = a_coeff->obj_quadratic_coeff;
        Float con_coeff = a_coeff->obj_constant_coeff;
        Float linear_coeff_value = con_coeff;
        int li_var_idx;
        int num_roots;
        // pcon < 0 ,quar >0   1 1 0    1 + 2 -
        // pcon < 0 ,quar <0   1 0 1    1 - 2+
        // pcon > 0 ,quar >0   0 1 1    1 - 2+
        // pcon > 0, quar <0   0 0 0    1 + 2-
        //  0 means 1+ 2 -    1means 1-2+ 
        //TODO: 1.精度问题 2. 等式应该是往左还是往右问题 3.int bin没考虑 4.算出来的root 有没有损失一些精度,可以考虑，先像整数靠拢，或者只取2位小数?
        // 1.bin没有考虑，2.精度问题 3.没有考虑实数的向上向下取整问题
        bool both_multi = false;
        Float multi_coeff;
        // _cur_assignment[var_pos] += change_value_1; 
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            if (li_var_idx == var_pos) 
            {
                both_multi = true;
                multi_coeff = li_var_coeff;
            }
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        if (true)
        {
            if (a_coeff->obj_quadratic_coeff != 0)
            {
                // return;
                // cout << "her ";
                double roots[2];
                Float delta_poly = - delta 
                                    - (linear_coeff_value * (_cur_assignment[var_idx])) 
                                    - (quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx]);
                num_roots = gsl_poly_solve_quadratic(quar_coeff, linear_coeff_value, delta_poly, &roots[0], &roots[1]);
                // cout <<" pcon->value " <<  pcon->value << " pcon->bound " << pcon->bound << "  linear_coeff_value * (_cur_assignment[var_idx]) " << linear_coeff_value * (_cur_assignment[var_idx]) << "  quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx] " << quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx];
                // cout <<" 变量为: " <<  _vars[var_idx].name << " a = " << quar_coeff << "  b = : " << linear_coeff_value << "  c =: " << delta_poly;
                // cout << delta_poly << endl;
                //感觉这里的条件给的太紧了，可以再想想
                // num_roots = gsl_poly_solve_quadratic(-pcon->bound, linear_coeff_value, quar_coeff, &roots[0], &roots[1]);
                if (num_roots == 2) 
                {
                    // std::cout << "Root 1: " << roots[0] << std::endl;
                    // std::cout << "Root 2: " << roots[1] << std::endl;
                    if (roots[0] > roots[1]) std::swap(roots[0], roots[1]);
                    if (_vars[var_idx].is_int)
                    {
                        bool addsub_case = (pcon->is_less) ^ (quar_coeff > 0);
                        if (pcon->is_equal)
                        {
                            if (roots[0] != std::floor(roots[0]) || roots[1] != std::floor(roots[1]))
                                return ;
                        }
                        else if (addsub_case)
                        {
                            roots[0] = std::floor(roots[0]);
                            roots[1] = std::ceil(roots[1]);
                        }
                        else 
                        {
                            roots[0] = std::ceil(roots[0]);
                            roots[1] = std::floor(roots[1]);
                        }
                    }
                    Float root_avg = (roots[0] + roots[1]) / 2;
                    roots[0] -= _cur_assignment[var_idx];
                    roots[1] -= _cur_assignment[var_idx];
                    if (check_var_shift(var_idx, roots[0], rand_flag))
                    {
                        // _operation_vars.push_back(var_idx);
                        // _operation_value.push_back(roots[0]);
                        pair_vars cur(var_pos, var_idx, change_value_1, roots[0]);
                        _operation_vars_pair.push_back(cur);
                        if (_constraint_tabu_enabled) {
                            _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        }
                    }
                    if (check_var_shift(var_idx, roots[1], rand_flag))
                    {
                        // _operation_vars.push_back(var_idx);
                        // _operation_value.push_back(roots[1]);
                        pair_vars cur(var_pos, var_idx, change_value_1, roots[1]);
                        _operation_vars_pair.push_back(cur);
                        if (_constraint_tabu_enabled) {
                            _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        }
                    }
                    // if (check_var_shift(var_idx, root_avg, rand_flag))
                    // {
                    //     _operation_vars.push_back(var_idx);
                    //     _operation_value.push_back(roots[3]);
                    // }
                } 
                else if (num_roots == 1) 
                {
                    // std::cout << "Single root: " << roots[0] << std::endl;
                    if (_vars[var_idx].is_int)
                    {
                        // Float sum1 = pcon->value + linear_coeff_value * ceil(roots[0]) + quar_coeff * ceil(roots[0]) * ceil(roots[0]);
                        // Float sum2 = pcon->value + linear_coeff_value * floor(roots[0]);
                        //
                        Float sum1 = pcon->value + linear_coeff_value * (ceil(roots[0]) - _cur_assignment[var_idx]) + quar_coeff * (ceil(roots[0]) * ceil(roots[0]) 
                        - _cur_assignment[var_idx] * _cur_assignment[var_idx]);
                        Float sum2 = pcon->value + linear_coeff_value * (floor(roots[0]) - _cur_assignment[var_idx]) + quar_coeff * (floor(roots[0]) * floor(roots[0]) 
                        - _cur_assignment[var_idx] * _cur_assignment[var_idx]);
                        if (pcon->is_equal && roots[0] != floor(roots[0])) return ;
                        else if (pcon->is_less)
                        {
                            if (sum1 <= pcon->bound) roots[0] = ceil(roots[0]);
                            else roots[0] = floor(roots[0]);
                        }
                        else 
                        {
                            if (sum1 >= pcon->bound) roots[0] = ceil(roots[0]);
                            else roots[0] = floor(roots[0]);
                        }
                        roots[0] -= _cur_assignment[var_idx];
                    }
                    roots[0] -= _cur_assignment[var_idx];
                    if (check_var_shift(var_idx, roots[0], rand_flag))
                    {
                        // _operation_vars.push_back(var_idx);
                        // _operation_value.push_back(roots[0]);
                        pair_vars cur(var_pos, var_idx, change_value_1, roots[0]);
                        _operation_vars_pair.push_back(cur);
                        if (_constraint_tabu_enabled) {
                            _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        }
                    }
                } 
                else 
                {
                    //因为精度导致的有解？
                    // cout << " wujie " << endl;
                }
            }
            else 
            {
                if (linear_coeff_value != 0) //不能太小
                {
                    // cout <<"delta "<< delta;
                    change_value = delta / (linear_coeff_value);
                    if (_vars[var_idx].is_int)
                    {
                        Float sum1 = pcon->value + linear_coeff_value * ceil(change_value);
                        Float sum2 = pcon->value + linear_coeff_value * floor(change_value);
                        if (pcon->is_equal && change_value != floor(change_value)) return ;
                        else if (pcon->is_less)
                        {
                            if (sum1 <= pcon->bound) change_value = ceil(change_value);
                            else change_value = floor(change_value);
                        }
                        else 
                        {
                            if (sum1 >= pcon->bound) change_value = ceil(change_value);
                            else change_value = floor(change_value);
                        }
                    }
                    if (check_var_shift(var_idx, change_value, rand_flag))
                    {
                        // _operation_vars.push_back(var_idx);
                        // _operation_value.push_back(change_value);
                        pair_vars cur(var_pos, var_idx, change_value_1, change_value);
                        _operation_vars_pair.push_back(cur);
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        // if (change_value==0)
                        //     cout <<"here "<< change_value;
                    }
                }
                if (pcon->is_average)
                {
                    if (pcon->sum == 0)
                    {
                        return;
                    }
                    Float average_change_value = change_value * (fabs(linear_coeff_value) / (pcon->sum));
                    if (check_var_shift(var_idx, average_change_value, rand_flag))
                    {
                        pair_vars cur(var_pos, var_idx, change_value_1, average_change_value);
                        _operation_vars_pair.push_back(cur);
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                    }
                }
            }
        }
        // _cur_assignment[var_pos] -= change_value_1; 
        // else 
        // {
        //     if (a_coeff->obj_quadratic_coeff != 0)
        //     {

        //     }
        //     else 
        //     {
        //         if ()
        //     }
        //     // 两者互为系数
        //     //再想想等式，小于，大于这里难道没有区别吗
        // }
    }

    bool qp_solver::compensate_move()
    {
        unordered_set<int> first_clause;
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        var * nor_var;
        polynomial_constraint * pcon;
        Float mono_delta;
        int var_pos;
        Float change_value;
        bool is_sat, is_post_sat;
        Float pcon_value;
        Float var_delta, con_delta;
        Float state;
        // var * nor_var;
        Float bound;
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_vars_pair.clear();
        if (_constraint_tabu_enabled) {
            _operation_cons_pos.clear();  // 清空约束位置映射
        }
        // if (_unsat_constraints.size() > 50)
        if (false)
        {
            while (first_clause.size() < 10)
            {
                unordered_set<int>::iterator it(_unsat_constraints.begin());
                std::advance(it, rand() % _unsat_constraints.size());
                first_clause.insert(*it);
            }
        }
        else if (_unsat_constraints.size() > 0)
        {
            for (int unsat_pos : _unsat_constraints)
            {
                first_clause.insert(unsat_pos);
            }
        }
        for (auto unsat_pos : first_clause)
        {
            unsat_con = & (_constraints[unsat_pos]);
            delta = unsat_con->bound - unsat_con->value;
            for (auto var_coeff : unsat_con->var_coeff)
            {
                var_idx = var_coeff.first;
                a_coeff = & (var_coeff.second);
                if (_vars[var_idx].is_bin) 
                    insert_var_change_value_bin(var_idx, a_coeff, 0, unsat_con, false);
                else 
                    insert_var_change_value(var_idx, a_coeff, delta, unsat_con, false);
            }
        }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            // 注意：这里不应该添加 _operation_cons_pos，因为 compensate_move 函数只处理 _operation_vars_pair
        }
        
        // 清空 _operation_cons_pos，因为第一个循环添加的条目对应 _operation_vars，不是 _operation_vars_pair
        // 第二个循环会重新添加对应 _operation_vars_pair 的条目
        if (_constraint_tabu_enabled) {
            _operation_cons_pos.clear();
        }
        for (int i = 0; i < _operation_vars.size(); i++)
        {
            var_pos = _operation_vars[i];
            nor_var = & (_vars[var_pos]);
            change_value = _operation_value[i];
            _cur_assignment[var_pos] += change_value;
            for (int con_size : nor_var->constraints)
            {
                pcon = & (_constraints[con_size]);
                // if (pcon->is_quadratic) continue;
                mono_delta = 0;
                for (int mono_pos = 0; mono_pos < pcon->monomials.size(); mono_pos++)
                {
                    mono_delta += pro_mono(pcon->monomials[mono_pos]);
                }
                pcon_value = mono_delta;
                bound = pcon->bound;
                delta = bound - pcon_value;
                is_sat = pcon->is_sat;
                if (pcon->is_equal) is_post_sat = (pcon_value >= bound - eb && pcon_value <= bound + eb);
                // else continue;
                else if (pcon->is_less) is_post_sat = (pcon_value <= bound + eb);
                else is_post_sat = (pcon_value >= bound - eb);
                // is_post_sat = (pcon_value >= bound - eb && pcon_value <= bound + eb);
                if (is_sat && !is_post_sat)
                // if (!is_post_sat)
                {
                    for (auto var_coeff : pcon->var_coeff)
                    {
                        var_idx = var_coeff.first;
                        if (var_idx == var_pos) continue;
                        a_coeff = & (var_coeff.second);
                        if (_vars[var_idx].is_bin) 
                            insert_var_change_value_comp_bin(var_pos, change_value, var_idx, a_coeff, 0, pcon, true);
                        else 
                            insert_var_change_value_comp(var_pos, change_value, var_idx, a_coeff, delta, pcon, true);
                    }
                }
            }
            _cur_assignment[var_pos] -= change_value;
        }
        int var_idx_1, var_idx_2;
        Float shift_1, shift_2;
        Float score;
        select_best_operation_with_pair_mix(var_idx_1, shift_1, var_idx_2, shift_2, score);
        if (score > 0)
        {
            // cout << _vars[var_idx_1].name << " " << shift_1 << " another:";
            // cout << _vars[var_idx_2].name << " " << shift_2 << endl;
            execute_critical_move_mix(var_idx_1, shift_1);
            execute_critical_move_mix(var_idx_2, shift_2);
            return true;
        }
        else return false;
    }
    
    void qp_solver::insert_operation_balance()
    {
        polynomial_constraint * unbound_con;
        all_coeff * a_coeff;
        var * obj_var;
        int var_idx;
        Float delta;
        Float linear_coeff_value = 0;
        Float li_var_coeff;
        int li_var_idx;
        Float best_value;
        Float cur_value;
        int symflag = 0; // 1 means a > 0 ,-1 means a < 0; 
        int op_num;
        Float change_value;
        bool continue_flag = false;
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_vars_pair.clear();
        _operation_cons_pos.clear();  // 清空约束位置映射
        _obj_vars_in_unbounded_constraint.clear();//TODO:改成两个
        _obj_bin_vars_in_unbounded_constraint.clear();//TODO:改成两个
        for (int var_pos : _vars_in_obj)
        {
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            if (_vars[var_pos].is_bin)
            {
                continue_flag = false;
                change_value = (cur_value == 0) ? 1 : -1;
                op_num = _operation_vars_sub.size();
                linear_coeff_value = obj_var->obj_constant_coeff;
                for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
                {
                    li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                    li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                    linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
                }
                linear_coeff_value += obj_var->obj_quadratic_coeff;
                if (linear_coeff_value == 0) continue_flag = true;
                if (linear_coeff_value > 0 && cur_value == 0) continue_flag = true;
                if (linear_coeff_value < 0 && cur_value == 1) continue_flag = true;
                // 这里再好好想想，是不是要维护可满足性质呢？
                //TODO:采样目标函数，要不太大了，目标函数感觉要用CY学姐的
                for (int con_pos: obj_var->constraints)
                {
                    unbound_con = & (_constraints[con_pos]);
                    a_coeff = &(unbound_con->var_coeff[var_pos]);
                    // cout <<"1: "<< unbound_con->name<< endl;
                    if (unbound_con->is_equal && unbound_con->is_linear) 
                    // if (unbound_con->is_equal && unbound_con->is_linear) 
                    {
                        // cout <<"2: "<< unbound_con->name<< endl;
                        if (insert_var_change_value_balance(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    else if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end() && unbound_con->is_linear)
                    {
                        if (insert_var_change_value_balance(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (continue_flag) continue;
                        if (insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false)) //TODO:check
                            _obj_bin_vars_in_unbounded_constraint.insert(var_pos);
                        
                    }
                }
            }
            else 
            {
                op_num = _operation_vars.size();
                linear_coeff_value = obj_var->obj_constant_coeff;
                for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
                {
                    li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                    li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                    linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
                }
                if (obj_var->obj_quadratic_coeff == 0)
                {
                    symflag = 0;
                    if (linear_coeff_value > 0) best_value = INT32_MIN;
                    else if (linear_coeff_value < 0) best_value = INT32_MAX;
                    else continue;     
                }
                else 
                {
                    if (obj_var->obj_quadratic_coeff > 0) symflag = 1;
                    else symflag = -1;
                    best_value = linear_coeff_value / ( - 2 * obj_var->obj_quadratic_coeff);
                }
                if (obj_var->constraints.size() == 0)
                {
                    no_cons_int_flag = true;
                    if (symflag == 1)
                    {
                        Float best_axis;
                        if (_vars[var_pos].is_int) 
                        {
                            best_axis = round(best_value);
                        best_axis = best_axis - _cur_assignment[var_pos];
                        }
                        else
                        {
                            best_axis = best_value - _cur_assignment[var_pos];
                        }
                        if (check_var_shift(var_pos, best_axis, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_axis);
                            if (_constraint_tabu_enabled) {
                                _operation_cons_pos.push_back(-1);  // 没有约束关联
                            }
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                        }
                    }
                    else if (best_value = INT32_MIN)
                    {
                        best_value = -1;
                        if (check_var_shift(var_pos, best_value, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_value);
                            if (_constraint_tabu_enabled) {
                                _operation_cons_pos.push_back(-1);  // 没有约束关联
                            }
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                        }
                    }
                    else if (best_value == INT32_MAX)
                    {
                        best_value = 1;
                        if (check_var_shift(var_pos, best_value, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_value);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                        }
                    }
                }
                for (int con_pos: obj_var->constraints)
                {
                    unbound_con = & (_constraints[con_pos]);
                    a_coeff = &(unbound_con->var_coeff[var_pos]);
                    if (unbound_con->is_equal && unbound_con->is_linear) 
                    {
                        if (insert_var_change_value_balance_rf(var_pos, unbound_con, symflag, best_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    else if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end() && unbound_con->is_linear)
                    {
                        if (insert_var_change_value_balance_rf(var_pos, unbound_con, symflag, best_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (unbound_con->is_equal) continue;
                        delta = unbound_con->bound - unbound_con->value;
                        a_coeff = &(unbound_con->var_coeff[var_pos]);
                        // 注意：insert_var_change_value_sat 是为 _operation_vars 设计的，不是为 _operation_vars_pair 设计的
                        // 这里应该使用专门为 _operation_vars_pair 设计的函数，或者修改逻辑
                        // 暂时注释掉这个调用，因为它会导致 _operation_cons_pos 大小不匹配
                        // insert_var_change_value_sat(var_pos, a_coeff, delta, unbound_con, symflag, best_value, false);
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                }
                op_num = _operation_vars.size() - op_num;
                if (op_num == 0 && symflag == 1)
                // if (symflag == 1)
                {
                    Float best_axis;
                    if (_vars[var_pos].is_int) 
                    {
                        best_axis = round(best_value);
                    best_axis = best_axis - _cur_assignment[var_pos];
                    }
                    else
                    {
                        best_axis = best_value - _cur_assignment[var_pos];
                    }
                    if (check_var_shift(var_pos, best_axis, false))
                    {
                        _operation_vars.push_back(var_pos);
                        _operation_value.push_back(best_axis);
                        _operation_cons_pos.push_back(-1);  // 没有约束关联
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                }
                if (symflag == 0)
                {
                    Float best_bound;
                    if (best_value == INT32_MAX && _vars[var_pos].has_upper)
                    {
                        best_bound = _vars[var_pos].upper - _cur_assignment[var_pos];
                        if (check_var_shift(var_pos, best_bound, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_bound);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                    if (best_value == INT32_MIN && _vars[var_pos].has_lower)
                    {
                        best_bound = _vars[var_pos].lower - _cur_assignment[var_pos];
                        if (check_var_shift(var_pos, best_bound, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_bound);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                }
            }
        }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            // 注意：_operation_cons_pos 已经在 insert_var_change_value_sat_bin 中添加了对应的条目
            // 这里不需要再添加，因为 _operation_vars_sub 对应的 _operation_cons_pos 条目已经存在
        }
        // for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") cout << " ??????";
        // }
    }

    bool qp_solver::insert_var_change_value_balance_rf(int var_idx, polynomial_constraint * pcon, int symflag, Float symvalue, bool rand_flag)
    {
        //这个函数写好，想好在哪里用
        //两个变量都在目标函数的情况，一个在一个不在
        //进这个函数的条件是目标变量一定能让目标函数下降
        // cout <<"3: "<< pcon->name << endl;
        // return false;
        Float sub_change_value;
        Float change_value = INT32_MAX;
        if (symflag == 1) change_value = symvalue - _cur_assignment[var_idx];
        else if (symflag == 0)
        {
            if (symvalue == INT32_MIN && _vars[var_idx].has_lower) change_value = _vars[var_idx].lower - _cur_assignment[var_idx];
            if (symvalue == INT32_MAX && _vars[var_idx].has_upper) change_value = _vars[var_idx].upper - _cur_assignment[var_idx];
        }
        if (_vars[var_idx].is_int) 
        {
            change_value = round(change_value);
            // 检查四舍五入后的值是否仍然满足约束
            if (change_value == INT32_MAX) return false;
        }
        all_coeff * first_coeff = &(pcon->var_coeff[var_idx]);
        var * second_var;
        bool is_have = false;
        if (!pcon->is_linear) return false;
        if (pcon->p_bin_vars.size() == 0 && change_value == INT32_MAX) return false;
        // if (pcon->p_bin_vars.size() == pcon->var_coeff.size()) return false;
        for (auto coeff : pcon->var_coeff)
        {
            second_var = & _vars[coeff.first];
            if (coeff.first == var_idx) continue;
            // 检查约束是否在tabu状态
            if (_constraint_tabu_enabled && is_constraint_tabu(pcon->index)) continue;
            Float change_value = INT32_MAX;
            if (symflag == 1) change_value = symvalue - _cur_assignment[var_idx];
            else if (symflag == 0)
            {
                if (symvalue == INT32_MIN && _vars[var_idx].has_lower) change_value = _vars[var_idx].lower - _cur_assignment[var_idx];
                if (symvalue == INT32_MAX && _vars[var_idx].has_upper) change_value = _vars[var_idx].upper - _cur_assignment[var_idx];
            }
            if (second_var->is_bin)
            {
                sub_change_value = (_cur_assignment[coeff.first] == 0) ? 1 : -1;
                change_value = (- sub_change_value * coeff.second.obj_constant_coeff) / first_coeff->obj_constant_coeff;
                if (_vars[var_idx].is_int && ceil(change_value) != change_value) continue;
                // if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, sub_change_value) >= 0) continue;
                if (_vars[coeff.first].is_in_obj) continue;
                if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, sub_change_value) >= 0) continue;
                if (check_var_shift(var_idx, change_value, true))
                {
                    // cout << _vars[var_idx].name << " " << _vars[coeff.first].name << endl;
                    pair_vars cur(var_idx, coeff.first, change_value, sub_change_value);
                    _operation_vars_pair.push_back(cur);
                    if (_constraint_tabu_enabled) {
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                    }
                    is_have = true;
                }
            }
            else 
            {
                //有问题，没考虑delta
                continue;
                if (change_value == INT32_MAX) continue;
                if (pcon->is_equal)
                    sub_change_value = (- change_value * first_coeff->obj_constant_coeff) / coeff.second.obj_constant_coeff;
                else 
                {
                    Float post_val = pcon->value + change_value * first_coeff->obj_constant_coeff;
                    if ((pcon->is_less && post_val > pcon->bound) || (!pcon->is_less && post_val < pcon->bound))
                    {
                        sub_change_value = (pcon->bound - post_val) / coeff.second.obj_constant_coeff;
                    }
                    // continue;
                }
                if (check_var_shift(var_idx, change_value, true) && check_var_shift(coeff.first, sub_change_value, true))
                {
                    if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, sub_change_value) >= 0) continue;
                    pair_vars cur(var_idx, coeff.first, change_value, sub_change_value);
                    // cout << change_value << " "  << sub_change_value << endl;
                    _operation_vars_pair.push_back(cur);
                    if (_constraint_tabu_enabled) {
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                    }
                    is_have = true;
                }
            }
        }
        return is_have;
        
    }

    bool qp_solver::insert_var_change_value_balance(int var_idx, all_coeff * a_coeff, Float delta_unused, polynomial_constraint * pcon, Float symvalue, bool rand_flag)
    {
        //这个函数写好，想好在哪里用
        //两个变量都在目标函数的情况，一个在一个不在
        //进这个函数的条件是目标变量一定能让目标函数下降
        // cout <<"3: "<< pcon->name << endl;
        Float sub_change_value;
        Float change_value = (_cur_assignment[var_idx] == 0) ? 1 : -1;
        all_coeff * first_coeff = &(pcon->var_coeff[var_idx]);
        bool is_have = false;
        if (!pcon->is_linear) return false;
        if (pcon->p_bin_vars.size() == 0) return false;
        // if (pcon->p_bin_vars.size() == pcon->var_coeff.size()) return false;
        for (auto coeff : pcon->var_coeff)
        {
            if (coeff.first == var_idx) continue;
            // 检查约束是否在tabu状态
            if (_constraint_tabu_enabled && is_constraint_tabu(pcon->index)) continue;
            sub_change_value = (- change_value * first_coeff->obj_constant_coeff) / coeff.second.obj_constant_coeff;
            // if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, sub_change_value) >= 0) continue;
            if (_vars[coeff.first].is_bin) 
            {
                Float could_change = (_cur_assignment[coeff.first] == 0) ? 1 : -1;
                // cout << pcon->name << endl;
                // cout << _vars[var_idx].name << " " << _vars[coeff.first].name << endl;
                // cout << sub_change_value  << " " << could_change << endl;
                if (could_change * coeff.second.obj_constant_coeff == - change_value * first_coeff->obj_constant_coeff)
                // if (sub_change_value == could_change)
                {
                    // cout << _vars[var_idx].name << " " << _vars[coeff.first].name << endl;
                    if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, could_change) >= 0) continue;
                    pair_vars cur(var_idx, coeff.first, change_value , could_change);
                    _operation_vars_pair.push_back(cur);
                    if (_constraint_tabu_enabled) {
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                    }
                    is_have = true;
                }
            }
            else
            {
                Float post_val = _cur_assignment[coeff.first] + sub_change_value;
                if (_vars[coeff.first].is_int) 
                {
                    if (ceil(sub_change_value) != sub_change_value)
                        continue;
                }
                if (calculate_obj_descent_two_vars_mix(var_idx, change_value, coeff.first, sub_change_value) >= 0) continue;
                bool lower_sat = !_vars[coeff.first].has_lower || post_val >= _vars[coeff.first].lower;
                bool upper_sat = !_vars[coeff.first].has_upper || post_val <= _vars[coeff.first].upper;
                if (lower_sat && upper_sat)
                {
                    // cout << _vars[var_idx].name << " " << _vars[coeff.first].name << endl;
                    pair_vars cur(var_idx, coeff.first, change_value , sub_change_value);
                    _operation_vars_pair.push_back(cur);
                    if (_constraint_tabu_enabled) {
                        _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                    }
                    is_have = true;
                }
            }
        }
        return is_have;
        
    }

    void qp_solver::random_walk_balance()
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
        int no_operation_var = rand() % _vars.size();
        Float cur_value;
        Float change_value;
        int op_num;
        bool continue_flag = false;
        unordered_set<int> rand_obj_idx;
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_vars_pair.clear();
        if (_constraint_tabu_enabled) {
            _operation_cons_pos.clear();  // 清空约束位置映射
        }
        // cout << _obj_vars_in_unbounded_constraint.size() << endl;
        // cout << _obj_bin_vars_in_unbounded_constraint.size() << endl;
        if (_obj_vars_in_unbounded_constraint.size() != 0)
        {
            for (int i = 0; i < rand_num_obj; i++) 
            {
                unordered_set<int>::iterator it(_obj_vars_in_unbounded_constraint.begin());
                std::advance(it, rand() % _obj_vars_in_unbounded_constraint.size());
                rand_obj_idx.insert(*it);
                if (i == 0) no_operation_var = *it; 
            }
        }
        if (_obj_bin_vars_in_unbounded_constraint.size() != 0)
        {
            for (int i = 0; i < rand_num_obj; i++) 
            {
                unordered_set<int>::iterator it(_obj_bin_vars_in_unbounded_constraint.begin());
                std::advance(it, rand() % _obj_bin_vars_in_unbounded_constraint.size());
                rand_obj_idx.insert(*it);
                if (i == 0) no_operation_var = *it; 
            }
        }
        for (int var_pos : rand_obj_idx)
        {
            if (!_vars[var_pos].is_bin) 
            {
                // if (_vars[var_pos].name =="b1") cout << ".....";
                bool add_flag = false;
                bool sub_flag = false;
                op_num = _operation_vars.size();
                obj_var = & (_vars[var_pos]);
                linear_coeff_value = obj_var->obj_constant_coeff;
                for (int linear_pos = 0; linear_pos < obj_var->obj_linear_coeff.size(); linear_pos++)
                {
                    li_var_idx = obj_var->obj_linear_coeff[linear_pos];
                    li_var_coeff = obj_var->obj_linear_constant_coeff[linear_pos];
                    if (_cur_assignment[li_var_idx] * li_var_coeff > 0) sub_flag = true;
                    else if (_cur_assignment[li_var_idx] * li_var_coeff < 0) add_flag = true;
                    linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
                }
                if (obj_var->obj_quadratic_coeff == 0)
                {
                    symflag = 0;
                    if (linear_coeff_value > 0) best_value = INT32_MIN;
                    else if (linear_coeff_value < 0) best_value = INT32_MAX; 
                    else continue;
                }
                else 
                {
                    if (obj_var->obj_quadratic_coeff > 0) symflag = 1;
                    else symflag = -1;
                    best_value = linear_coeff_value / ( - 2 * obj_var->obj_quadratic_coeff);
                }
                if (obj_var->constraints.size() == 0)
                {
                    if (add_flag)
                    {
                        best_value = 1;
                        if (check_var_shift(var_pos, best_value, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_value);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                    else if (sub_flag)
                    {
                        best_value = -1;
                        if (check_var_shift(var_pos, best_value, false))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_value);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                }
                for (int con_pos: obj_var->constraints)
                {
                    unbound_con = & (_constraints[con_pos]);
                    a_coeff = &(unbound_con->var_coeff[var_pos]);
                    if (unbound_con->is_equal && unbound_con->is_linear) 
                    {
                        if (insert_var_change_value_balance_rf(var_pos, unbound_con, symflag, best_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    else if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end() && unbound_con->is_linear)
                    {
                        if (insert_var_change_value_balance_rf(var_pos, unbound_con, symflag, best_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (unbound_con->is_equal) continue;
                        delta = unbound_con->bound - unbound_con->value;
                        a_coeff = &(unbound_con->var_coeff[var_pos]);
                        // 注意：insert_var_change_value_sat 是为 _operation_vars 设计的，不是为 _operation_vars_pair 设计的
                        // 这里应该使用专门为 _operation_vars_pair 设计的函数，或者修改逻辑
                        // 暂时注释掉这个调用，因为它会导致 _operation_cons_pos 大小不匹配
                        // insert_var_change_value_sat(var_pos, a_coeff, delta, unbound_con, symflag, best_value, true);
                    }
                }
                op_num = _operation_vars.size() - op_num;
                if (op_num == 0 && symflag == 1)
                // if (symflag == 1)
                {
                    Float best_shift;
                    if (_vars[var_pos].is_int) 
                    {
                        best_shift = round(best_value) - _cur_assignment[var_pos];
                    }
                    else
                    {
                        best_shift = best_value - _cur_assignment[var_pos];
                    }
                    if (check_var_shift(var_pos, best_shift, true))
                    {
                        _operation_vars.push_back(var_pos);
                        _operation_value.push_back(best_shift);
                        _operation_cons_pos.push_back(-1);  // 没有约束关联
                    }
                }
                if (symflag == 0)
                {
                    Float best_bound;
                    if (best_value == INT32_MAX && _vars[var_pos].has_upper)
                    {
                        best_bound = _vars[var_pos].upper - _cur_assignment[var_pos];
                        if (check_var_shift(var_pos, best_bound, true))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_bound);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                    if (best_value == INT32_MIN && _vars[var_pos].has_lower)
                    {
                        best_bound = _vars[var_pos].lower - _cur_assignment[var_pos];
                        if (check_var_shift(var_pos, best_bound, true))
                        {
                            _operation_vars.push_back(var_pos);
                            _operation_value.push_back(best_bound);
                            _operation_cons_pos.push_back(-1);  // 没有约束关联
                        }
                    }
                }
            }
            else if (_vars[var_pos].is_bin)
            {
                continue_flag = false;
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
                if (linear_coeff_value == 0) continue_flag = true;
                if (linear_coeff_value > 0 && cur_value == 0) continue_flag = true;
                if (linear_coeff_value < 0 && cur_value == 1) continue_flag = true;
                for (int con_pos: obj_var->constraints)
                {
                    unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                    a_coeff = &(unbound_con->var_coeff[var_pos]);
                    // if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    // {
                    //     insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, true);       
                    // }
                    if (unbound_con->is_equal && unbound_con->is_linear) 
                    {
                        insert_var_change_value_balance(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, true);
                    }
                    else if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end() && unbound_con->is_linear)
                    {
                        if (insert_var_change_value_balance(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, false));
                            _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                    if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (continue_flag) continue;
                        insert_var_change_value_sat_bin(var_pos, a_coeff, 0, unbound_con, linear_coeff_value, true);//TODO:check              
                    }
                }
            }
        }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            // 注意：_operation_cons_pos 已经在 insert_var_change_value_sat_bin 中添加了对应的条目
            // 这里不需要再添加，因为 _operation_vars_sub 对应的 _operation_cons_pos 条目已经存在
        }
        // int var_pos;
        // Float change_value_2, score;
        // select_best_operation_mix(var_pos, change_value_2, score);
        // if (score != INT32_MIN) execute_critical_move_mix(var_pos, change_value_2);
        // else no_operation_walk_sat(no_operation_var);



        int var_pos;
        Float change_value_2, score;
        select_best_operation_mix(var_pos, change_value_2, score);
        int var_pos_equal_1, var_pos_equal_2;
        Float var_1_change_value, var_2_change_value;
        Float score_equal;
        Float max_score;
        select_best_operation_with_pair_mix(var_pos_equal_1,  var_1_change_value, var_pos_equal_2, var_2_change_value, score_equal);
        max_score = std::max(score, score_equal);
        if (max_score != INT32_MIN) 
        {
            if (max_score == score)
                execute_critical_move_mix(var_pos, change_value_2);
            else 
            {
                execute_critical_move_mix(var_pos_equal_1, var_1_change_value);
                execute_critical_move_mix(var_pos_equal_2, var_2_change_value);
            }
        }
        else no_operation_walk_sat(no_operation_var);
    }

    void qp_solver::local_search_mix_balance()
    {
        cout << "mix_balance" << endl;
        // initialize_mix();
        sta_cons();
        restart_by_new_solution();//test
        
        // 启用约束级别的tabu机制
        // set_constraint_tabu_enabled(true);
        // int var_pos;
        int bin_var_pos;
        Float bin_score, score;
        Float change_value, bin_change_value;
        int var_pos, var_pos_equal_1, var_pos_equal_2;
        Float var_1_change_value, var_2_change_value, score_equal, max_score;
        bool mode;// 0 means bool, 1 means real;
        // sta_cons();
        for (_steps = 0; _steps <= _max_steps; _steps++)
        {
            //TODO
            if (_steps % 1000 == 0 && (TimeElapsed() > _cut_off)) break;
            if (is_cur_feasible)
            {
                insert_operation_balance();
                select_best_operation_mix(var_pos, change_value, score);
                select_best_operation_with_pair_mix(var_pos_equal_1, var_1_change_value, var_pos_equal_2, var_2_change_value, score_equal);
                max_score = std::max(score, score_equal);
                if (max_score > 0)
                {
                    if (score > 0 || max_score == score)
                    // if (max_score == score)
                        execute_critical_move_mix_more(var_pos, change_value);
                    else 
                    {
                        execute_critical_move_mix(var_pos_equal_1, var_1_change_value);
                        execute_critical_move_mix(var_pos_equal_2, var_2_change_value);
                    }
                }
                else 
                {
                    update_weight();
                    random_walk_balance();
                }
                // select_best_operation_lift(var_pos, change_value, score);
                // cout << "sat :  ";
                // if (score > 0) execute_critical_move_mix(var_pos, change_value);
                // else 
                // {
                //     update_weight();
                //     random_walk_sat_mix_not_dis();    
                // } 
            }
            else 
            {
                insert_operation_unsat_mix_not_dis();
                select_best_operation_mix(var_pos, change_value, score);
                // cout << score << endl;
                // cout << "unsat :  ";
                if (score > 0) execute_critical_move_mix_more(var_pos, change_value);
                else 
                {
                    if (!compensate_move())
                    // if (true)
                    {
                        update_weight();
                        random_walk_unsat_mix_not_dis();
                    }
                }
                
            }
        }
        if (_best_object_value == INT32_MAX) cout << INT64_MAX << endl;
        else
        {
            if (is_minimize)
                // cout << std::fixed << std::setprecision(15) << " best obj min= " ;
                cout << std::fixed << " best obj min= " ;
            else 
                // cout << std::fixed << std::setprecision(15) << " best obj max= " ;
                cout << std::fixed << " best obj max= " ;
            if (is_minimize) cout << _best_object_value + _obj_constant;
            else cout << -_best_object_value + _obj_constant;
            // cout << endl << " solution : " <<endl;
            // print_best_solution();
        }
    }

}