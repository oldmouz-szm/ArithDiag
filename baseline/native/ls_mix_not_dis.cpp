#include "sol.h"
namespace solver
{

    void qp_solver::sta_cons()
    {
        // add_bool_bound();
        int status = 0;
        int quad_eq_number = 0;
        int quad_neq_number = 0;
        int linear_eq_number = 0;
        int linear_neq_number = 0;
        vector <int> equal_long_cons;
        for (int i = 0; i < _constraints.size(); i++)
        {
            auto & con = _constraints[i];
            size_t cur_size = con.monomials.size();
            // if (con.is_equal && !con.is_quadratic && con.monomials.size() >= 10 && con.bound != 0) equal_long_cons.push_back(i);
            // if (!con.is_quadratic && con.monomials.size() >= 10 && con.bound != 0) equal_long_cons.push_back(i);
            bool quad_flag = false;
            bool is_average = (con.bound == 0) ?  false : true;
            Float sum = 0;
            int bool_num = 0;
            int all_num = 0;
            Float bool_coeff;
            for (auto mono : con.monomials)
            {
                if (!mono.is_linear) 
                {
                    quad_flag = true;
                    is_average = false;
                }
                for (auto var : mono.m_vars)
                {
                    if (_vars[var].is_bin || _vars[var].is_int) is_average = false;
                    if (_vars[var].is_bin) 
                    {
                        bool_coeff = -mono.coeff;
                        bool_num++;
                    }
                    else all_num++;
                }
                sum += fabs(mono.coeff);
            }
            // if (con.bound == 0) is_average = false;
            con.is_linear = !quad_flag;
            con.is_average = is_average;
            if (is_average) 
            {
                if (con.monomials.size() >= 10) equal_long_cons.push_back(i);
                con.sum = sum;
                // cout << con.name << endl;
            }
            else con.sum = 0;
            // if (!quad_flag && bool_coeff == 1 && all_num >= 5)
            // {
            //     con.sum = sum;
            //     con.is_average = true;
            // }
            if (con.is_equal && quad_flag) quad_eq_number++;
            else if (!con.is_equal && quad_flag) quad_neq_number++;
            else if (!con.is_equal && !quad_flag) linear_neq_number++;
            else if (con.is_equal && !quad_flag) linear_eq_number++;
            if (con.is_linear && con.is_equal && con.monomials.size() <= 3)
            {
                int idx_1, idx_2, idx_3;
                Float coeff_1, coeff_2, coeff_3;
                int bool_num = 0;
                // cout << con.name <<" "<< con.p_bin_vars.size() << endl;
                if (con.monomials.size() == 2)
                {
                    idx_1 = con.monomials[0].m_vars[0];
                    coeff_1 = con.monomials[0].coeff;
                    idx_2 = con.monomials[1].m_vars[0];
                    coeff_2 = con.monomials[1].coeff;
                    if (!_vars[idx_1].is_bin && !_vars[idx_1].is_bin)
                    {
                        equal_var cur_1(idx_2, -coeff_1 / coeff_2, con.bound / coeff_2);
                        // cout << _vars[idx_2].name << " " << -coeff_1 / coeff_2 << " " << con.bound / coeff_2 << endl;
                        _vars[idx_1].equal_pair.push_back(cur_1);
                        equal_var cur_2(idx_1, -coeff_2 / coeff_1, con.bound / coeff_1);
                        // cout << _vars[idx_1].name << " " << -coeff_2 / coeff_1 << " " << con.bound / coeff_1 << endl;
                        _vars[idx_2].equal_pair.push_back(cur_2);
                    }
                }
                else if (con.monomials.size() == 3) 
                {
                    idx_1 = con.monomials[0].m_vars[0];
                    coeff_1 = con.monomials[0].coeff;
                    idx_2 = con.monomials[1].m_vars[0];
                    coeff_2 = con.monomials[1].coeff;
                    idx_3 = con.monomials[2].m_vars[0];
                    coeff_3 = con.monomials[2].coeff;
                    if (_vars[idx_1].is_bin) bool_num++;
                    if (_vars[idx_2].is_bin) bool_num++;
                    if (_vars[idx_3].is_bin) bool_num++;
                    if (bool_num != 1) continue;
                    if (_vars[idx_1].is_bin)
                    {
                        std::swap(idx_1, idx_3);
                        std::swap(coeff_1, coeff_3);
                    }
                    else if (_vars[idx_2].is_bin)
                    {
                        std::swap(idx_2, idx_3);
                        std::swap(coeff_2, coeff_3);
                    }
                    equal_var cur_1(idx_2, -coeff_1 / coeff_2, idx_3, -coeff_3 / coeff_2, con.bound / coeff_2);
                    // cout <<_vars[idx_1].name<<" "<< _vars[idx_2].name << " " << -coeff_1 / coeff_2 << " " << _vars[idx_3].name << " " <<-coeff_3 / coeff_2 << " " << con.bound / coeff_2 << endl;
                    _vars[idx_1].equal_pair.push_back(cur_1);
                    equal_var cur_2(idx_1, -coeff_2 / coeff_1, idx_3, -coeff_3 / coeff_1, con.bound / coeff_1);
                    _vars[idx_2].equal_pair.push_back(cur_2);
                }
            }
        }
        unordered_map<int, Float> _init_solution_map_sub;
        bool is_avg_init = true;
        Float avg_value;
        for (auto max_index : equal_long_cons)
        {
            polynomial_constraint * max_length_con = &(_constraints[max_index]);
            is_avg_init = true;
            for (auto mono : max_length_con->monomials)
            {
                avg_value = (mono.coeff / max_length_con->sum) * max_length_con->bound;
                // if (max_length_con->is_average) cout << _vars[mono.m_vars[0]].name << " " << avg_value << endl;
                if (_vars[mono.m_vars[0]].has_upper && avg_value > _vars[mono.m_vars[0]].upper)
                {
                    is_avg_init = false;
                    break;
                }
                if (_vars[mono.m_vars[0]].has_lower && avg_value < _vars[mono.m_vars[0]].lower)
                {
                    is_avg_init = false;
                    break;
                }
                _init_solution_map_sub[mono.m_vars[0]] = avg_value;
            }
            if (is_avg_init) 
            {
                _init_solution_map = _init_solution_map_sub;
            }
            else 
            {
                max_length_con->is_average = false;
            }
        }
        // for (auto init : _init_solution_map)
        // {
        //     if (init.second != 0)
        //         cout << _vars[init.first].name << " " << init.second<< endl;
        // }
        if (quad_eq_number != 0)
            cout << " with quadratic equation " << endl;
        else if (linear_eq_number != 0)
            cout << " only with linear equation " << endl;
        else 
            cout << "without equation" << endl;
        // exit(0);
        // cout << "total constraint number: " << _constraints.size() << endl;
        // cout << "quadratic equation constraint number: " << quad_eq_number << endl;
        // cout << "quadratic inequation constraint number:" << quad_neq_number<< endl;
        // cout << "linear equation constraint number:" << linear_eq_number << endl;
        // cout << "linear inequation constraint number:" << linear_neq_number << endl;
    }

    void qp_solver::insert_var_change_value_sat(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, int symflag, Float symvalue, bool rand_flag)
    {
        // rand_flag = false;
        Float change_value;
        Float li_var_coeff;
        Float quar_coeff = a_coeff->obj_quadratic_coeff;
        Float con_coeff = a_coeff->obj_constant_coeff;
        Float linear_coeff_value = con_coeff;
        int li_var_idx;
        int num_roots;
        Float var_lb = INT32_MIN;
        Float var_up = INT32_MAX;
        bool is_less = pcon->is_less;
        // pcon < 0 ,quar >0 1 1 0 1 + 2 -
        // pcon < 0 ,quar <0 1 0 1 1 - 2+
        // pcon > 0 ,quar >0 0 1 1 1 - 2+
        // pcon > 0, quar <0 0 0 0 1 + 2-
        //  0 means 1+ 2 -    1means 1-2+ 
        //TODO: 1.精度问题 2. 等式应该是往左还是往右问题 3.int bin没考虑 4.算出来的root 有没有损失一些精度,可以考虑，先像整数靠拢，或者只取2位小数?
        // 1.bin没有考虑，2.精度问题 3.没有考虑实数的向上向下取整问题
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        if (a_coeff->obj_quadratic_coeff != 0)
        {
            double roots[2];
            Float delta_poly = pcon->value - (pcon->bound) 
                            - (linear_coeff_value * (_cur_assignment[var_idx])) 
                            - (quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx]);
            num_roots = gsl_poly_solve_quadratic(quar_coeff, linear_coeff_value, delta_poly, &roots[0], &roots[1]);
            if (num_roots == 2 && roots[0] != roots[1]) 
            {
                if (roots[0] > roots[1]) std::swap(roots[0], roots[1]);
                bool addsub_case = (pcon->is_less) ^ (quar_coeff > 0);
                if (_vars[var_idx].is_int)
                {
                    if (addsub_case)
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
                var_lb = roots[0];
                var_up = roots[1];
                if (symflag < 0) //可能分类分少了,没考虑约束的开口可行域，仔细看看阿里相关的部分
                {
                    Float best_bound;
                    // if (_vars[var_idx].has_lower)
                    // {
                    //     best_bound = _vars[var_idx].lower - _cur_assignment[var_idx];
                    //     if (check_var_shift(var_idx, best_bound, false))
                    //     {
                    //         _operation_vars.push_back(var_idx);
                    //         _operation_value.push_back(best_bound);
                    //     }
                    // }
                    // else 
                    if (fabs(roots[0] - symvalue) > fabs(_cur_assignment[var_idx] - symvalue))
                    {
                        roots[0] -= _cur_assignment[var_idx];
                        if (check_var_shift(var_idx, roots[0], rand_flag))
                        {
                            _operation_vars.push_back(var_idx);
                            _operation_value.push_back(roots[0]);
                            _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        }
                    }
                    // if (_vars[var_idx].has_upper)
                    // {
                    //     best_bound = _vars[var_idx].upper - _cur_assignment[var_idx];
                    //     if (check_var_shift(var_idx, best_bound, false))
                    //     {
                    //         _operation_vars.push_back(var_idx);
                    //         _operation_value.push_back(best_bound);
                    //     }
                    // }
                    // else 
                    if (fabs(roots[1] - symvalue) > fabs(_cur_assignment[var_idx] - symvalue))
                    {
                        roots[1] -= _cur_assignment[var_idx];
                        if (check_var_shift(var_idx, roots[1], rand_flag))
                        {
                            _operation_vars.push_back(var_idx);
                            _operation_value.push_back(roots[1]);
                            _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                        }
                    }

                }
                else if (symflag > 0)
                {
                    if (!addsub_case) //[a,b]
                    {
                        if (roots[1] < symvalue)
                        {
                            roots[1] -= _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, roots[1], rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(roots[1]);
                                _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                            }
                        }
                        else if (roots[1] >= symvalue && roots[0] <= symvalue)
                        {
                            // change_value = round(symvalue) - _cur_assignment[var_idx];
                            change_value = symvalue - _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, change_value, rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(change_value);
                                _operation_cons_pos.push_back(pcon->index);
                            }
                        }
                        else 
                        {
                            roots[0] -= _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, roots[0], rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(roots[0]);
                                _operation_cons_pos.push_back(pcon->index);
                            }
                        }
                    }
                    else  //[-inf,a] \cup [b,+inf]
                    {
                        if (roots[0] >= symvalue || roots[1] <= symvalue)
                        {
                            // change_value = round(symvalue) - _cur_assignment[var_idx];
                            change_value = symvalue - _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, change_value, rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(change_value);
                                _operation_cons_pos.push_back(pcon->index);
                            }
                        }
                        else
                        {
                            if (fabs(roots[0] - symvalue) < fabs(_cur_assignment[var_idx] - symvalue))
                            {
                                roots[0] -= _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, roots[0], rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(roots[0]);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                            if (fabs(roots[1] - symvalue) < fabs(_cur_assignment[var_idx] - symvalue))
                            {
                                roots[1] -= _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, roots[1], rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(roots[1]);
                                    _operation_cons_pos.push_back(pcon->index);  // 记录约束来源
                                }
                            }
                        }
                    }
                }
                else 
                {
                    if (symvalue > 0)
                    {
                        // roots[1] -= _cur_assignment[var_idx];
                        // if (check_var_shift(var_idx, roots[1], rand_flag))
                        // {
                        //     _operation_vars.push_back(var_idx);
                        //     _operation_value.push_back(roots[1]);
                        // }
                        if (!addsub_case)
                        {
                            change_value = roots[1] - _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, change_value, rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(change_value);
                                _operation_cons_pos.push_back(pcon->index);
                            }
                        }
                        else 
                        {
                            if (roots[1] > _cur_assignment[var_idx])
                            {
                                roots[1] -= _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, roots[1], rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(roots[1]);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                        }
                    }
                    else 
                    {
                        if (!addsub_case)
                        {
                            change_value = roots[0] - _cur_assignment[var_idx];
                            if (check_var_shift(var_idx, change_value, rand_flag))
                            {
                                _operation_vars.push_back(var_idx);
                                _operation_value.push_back(change_value);
                                _operation_cons_pos.push_back(pcon->index);
                            }
                        }
                        else 
                        {
                            if (roots[0] < _cur_assignment[var_idx])
                            {
                                roots[0] -= _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, roots[0], rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(roots[0]);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                        }
                    }
                }
            } 
            else if (num_roots == 1 || roots[0] == roots[1])// roots number = 0 不存在, roots number = 1 
            {
                bool addsub_case = (pcon->is_less) ^ (quar_coeff > 0);
                if (symflag > 0)
                {
                    if (addsub_case)
                    {
                        change_value = round(symvalue) - _cur_assignment[var_idx];
                        if (check_var_shift(var_idx, change_value, rand_flag))
                        {
                            _operation_vars.push_back(var_idx);
                            _operation_value.push_back(change_value);
                            _operation_cons_pos.push_back(pcon->index);
                        }
                    }
                }
                else if (symflag < 0)
                {
                    //do nothing
                }
                else 
                {
                    // do nothing
                }
            } 
        }
        else 
        {
            if (linear_coeff_value != 0) //不能太小
            {
                change_value = delta / (linear_coeff_value);
                bool addsub_case = (pcon->is_less) ^ (linear_coeff_value > 0);
                if (_vars[var_idx].is_int)
                {
                    Float sum1 = pcon->value + linear_coeff_value * ceil(change_value);
                    Float sum2 = pcon->value + linear_coeff_value * floor(change_value);
                    if (pcon->is_less)
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
                if (symflag == 0)
                {
                    // if (addsub_case)
                    // {
                    //     if (symvalue == INT32_MAX) 
                    //     {
                    //         if (_vars[var_idx].has_upper) change_value = _vars[var_idx].upper - _cur_assignment[var_idx];
                    //         else return;
                    //     }
                    //     else {}
                    // }
                    // else 
                    // {
                    //     if (symvalue == INT32_MIN) 
                    //     {
                    //         if (_vars[var_idx].has_lower) change_value = _vars[var_idx].lower - _cur_assignment[var_idx];
                    //         else return;
                    //     }
                    //     else {}
                    // }
                    if ((symvalue == INT32_MAX && change_value < 0) || (symvalue == INT32_MIN && change_value > 0)) return;
                    if (check_var_shift(var_idx, change_value, rand_flag))
                    {
                        _operation_vars.push_back(var_idx);
                        _operation_value.push_back(change_value);
                        _operation_cons_pos.push_back(pcon->index);
                    }
                }
                else 
                {
                    // pcon < 0 ,linear > 0  1 1 0 x<=k
                    // pcon < 0 ,linear < 0  1 0 1 x>=k
                    // pcon > 0 ,linear > 0  0 1 1 x>=k
                    // pcon > 0, linear < 0  0 0 0 x<=k
                    // bool addsub_case = (pcon->is_less) ^ (linear_coeff_value > 0);
                    if (!addsub_case)
                    {
                        //symvalue会不会过于大了
                        if (symflag > 0)
                        {
                            if (_cur_assignment[var_idx] + change_value >= symvalue)
                            {
                                if (_vars[var_idx].is_int) change_value = round(symvalue) - _cur_assignment[var_idx];//不能保证是整数,round肯定是用错了的,没有处理好round之后对称轴是不是在可行域内的事情。 对称轴是0.6，解到x<=0.5
                                else change_value = symvalue - _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, change_value, rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(change_value);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                            else 
                            {
                                //条件不要有,想了想还是得有的，可能是减法，并且直接用change_value的同时判断整数得
                                // if (fabs(_cur_assignment[var_idx] + change_value - symvalue) < fabs(_cur_assignment[var_idx] - symvalue))
                                if (1)
                                {
                                    if (check_var_shift(var_idx, change_value, rand_flag))
                                    {
                                        _operation_vars.push_back(var_idx);
                                        _operation_value.push_back(change_value);
                                        _operation_cons_pos.push_back(pcon->index);
                                    }
                                }
                            }
                        }
                        else
                        {
                            // //下面这个符号是应该是大于号,这种情况还要移动吗可以再考虑考虑
                            // if (_vars[var_idx].has_upper) 
                            // {
                            //     Float change_value_bound = _vars[var_idx].upper - _cur_assignment[var_idx];
                            //     if (check_var_shift(var_idx, change_value_bound, rand_flag))
                            //     {
                            //         _operation_vars.push_back(var_idx);
                            //         _operation_value.push_back(change_value_bound);
                            //     }
                            // }
                            // if (_vars[var_idx].has_lower)
                            // {
                            //     Float change_value_bound = _vars[var_idx].lower - _cur_assignment[var_idx];
                            //     if (check_var_shift(var_idx, change_value_bound, rand_flag))
                            //     {
                            //         _operation_vars.push_back(var_idx);
                            //         _operation_value.push_back(change_value_bound);
                            //     }
                            // } 
                            if (fabs(_cur_assignment[var_idx] + change_value - symvalue) > fabs(_cur_assignment[var_idx] - symvalue))
                            {
                                if (check_var_shift(var_idx, change_value, rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(change_value);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                        }
                    }
                    else 
                    {   //x>=k  change_value < 0
                        if (symflag > 0)
                        {
                            if (_cur_assignment[var_idx] + change_value <= symvalue)
                            {
                                if (_vars[var_idx].is_int) change_value = round(symvalue) - _cur_assignment[var_idx];//不能保证是整数,在整数的情况好像也没有考虑能不能满足
                                else change_value = symvalue - _cur_assignment[var_idx];
                                if (check_var_shift(var_idx, change_value, rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(change_value);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                            else 
                            {
                                // if (fabs(_cur_assignment[var_idx] + change_value - symvalue) < fabs(_cur_assignment[var_idx] - symvalue))
                                if (1)
                                {
                                    if (check_var_shift(var_idx, change_value, rand_flag))
                                    {
                                        _operation_vars.push_back(var_idx);
                                        _operation_value.push_back(change_value);
                                        _operation_cons_pos.push_back(pcon->index);
                                    }
                                }
                            }
                        }
                        else
                        {
                            // if (_vars[var_idx].has_upper) 
                            // {
                            //     Float change_value_bound = _vars[var_idx].upper - _cur_assignment[var_idx];
                            //     if (check_var_shift(var_idx, change_value_bound, rand_flag))
                            //     {
                            //         _operation_vars.push_back(var_idx);
                            //         _operation_value.push_back(change_value_bound);
                            //     }
                            // }
                            // if (_vars[var_idx].has_lower)
                            // {
                            //     Float change_value_bound = _vars[var_idx].lower - _cur_assignment[var_idx];
                            //     if (check_var_shift(var_idx, change_value_bound, rand_flag))
                            //     {
                            //         _operation_vars.push_back(var_idx);
                            //         _operation_value.push_back(change_value_bound);
                            //     }
                            // } 
                            if (fabs(_cur_assignment[var_idx] + change_value - symvalue) > fabs(_cur_assignment[var_idx] - symvalue))
                            {
                                if (check_var_shift(var_idx, change_value, rand_flag))
                                {
                                    _operation_vars.push_back(var_idx);
                                    _operation_value.push_back(change_value);
                                    _operation_cons_pos.push_back(pcon->index);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    void qp_solver::insert_var_change_value(int var_idx, all_coeff * a_coeff, Float delta, polynomial_constraint * pcon, bool rand_flag)
    {
        rand_flag = false;
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
        // if (quar_coeff == 0 && con_coeff == 0 && a_coeff->obj_linear_coeff.size() == 1)
        // {
        //     li_var_idx = a_coeff->obj_linear_coeff[0];
        //     change_value = 1;
        //     if (_cur_assignment[var_idx] == 0 && _cur_assignment[li_var_idx] == 0)
        //     {
        //         if (check_var_shift(var_idx, change_value, rand_flag))
        //         {
        //             _operation_vars.push_back(var_idx);
        //             _operation_value.push_back(change_value);
        //         }
        //     }
        // }
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            linear_coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        if (a_coeff->obj_quadratic_coeff != 0)
        {
            // cout << "her ";
            double roots[2];
            Float delta_poly = pcon->value - (pcon->bound) 
                                - (linear_coeff_value * (_cur_assignment[var_idx])) 
                                - (quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx]);
            num_roots = gsl_poly_solve_quadratic(quar_coeff, linear_coeff_value, delta_poly, &roots[0], &roots[1]);
            // cout <<" pcon->value " <<  pcon->value << " pcon->bound " << pcon->bound << "  linear_coeff_value * (_cur_assignment[var_idx]) " << linear_coeff_value * (_cur_assignment[var_idx]) << "  quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx] " << quar_coeff * _cur_assignment[var_idx] * _cur_assignment[var_idx];
            // cout <<" 变量为: " <<  _vars[var_idx].name << " a = " << quar_coeff << "  b = : " << linear_coeff_value << "  c =: " << delta_poly;
            // cout << delta_poly << endl;
            //感觉这里的条件给的太紧了，可以再想想
            // num_roots = gsl_poly_solve_quadratic(-pcon->bound, linear_coeff_value, quar_coeff, &roots[0], &roots[1]);
            bool addsub_case = (pcon->is_less) ^ (quar_coeff > 0);
            Float root_avg = linear_coeff_value / (-2 * quar_coeff); 
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
                root_avg -= _cur_assignment[var_idx];
                if (check_var_shift(var_idx, roots[0], rand_flag))
                {
                    _operation_vars.push_back(var_idx);
                    _operation_value.push_back(roots[0]);
                    _operation_cons_pos.push_back(pcon->index);
                }
                if (check_var_shift(var_idx, roots[1], rand_flag))
                {
                    _operation_vars.push_back(var_idx);
                    _operation_value.push_back(roots[1]);
                    _operation_cons_pos.push_back(pcon->index);
                }
                // if (!addsub_case && check_var_shift(var_idx, root_avg, rand_flag))
                // {
                //     _operation_vars.push_back(var_idx);
                //     _operation_value.push_back(root_avg);
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
                    _operation_vars.push_back(var_idx);
                    _operation_value.push_back(roots[0]);
                    _operation_cons_pos.push_back(pcon->index);
                }
            } 
            else 
            {
                // roots[0] = / (-2 * quar_coeff)
                //因为精度导致的有解？
                // cout << " wujie " << endl;
                // root_avg -= _cur_assignment[var_idx];
                // if (!addsub_case && check_var_shift(var_idx, root_avg, rand_flag))
                // {
                //     _operation_vars.push_back(var_idx);
                //     _operation_value.push_back(root_avg);
                // }
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
                    _operation_vars.push_back(var_idx);
                    _operation_value.push_back(change_value);
                    _operation_cons_pos.push_back(pcon->index);
                    // if (change_value==0)
                    //     cout <<"here "<< change_value;
                }
                if (pcon->is_average)
                {
                    if (pcon->sum == 0)
                    {
                        // cout << "error with sum = 0" << endl; //负的情况也考虑考虑，以及tabu，传播的流程以及可行性
                        // exit(0);
                        return;
                    }
                    // cout << "here" << endl;
                    Float average_change_value = change_value * (fabs(linear_coeff_value) / (pcon->sum));
                    // cout <<" start: " << average_change_value <<"   "<< linear_coeff_value << "  " << (pcon->sum)<< endl;
                    // cout << average_change_value << endl;
                    if (check_var_shift(var_idx, average_change_value, rand_flag))
                    {
                        _operation_vars.push_back(var_idx);
                        _operation_value.push_back(average_change_value);
                        _operation_cons_pos.push_back(pcon->index);
                    }
                }
            }
        }
    }
    // sss
    void qp_solver::initialize_mix()
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
        unsat_cls_num_with_bool = 0;
        unsat_cls_num_with_real = 0;
        if (_constraints.size() != 0) avg_bound /= _constraints.size();
        //构建LS的信息,类里其它信息的构建,初始值的给出,约束的满足和不满足,初始化二进制变量的score:
        if (problem_type != 0)
        {
            // for (int i = 0; i < _var_num; i++)
            // {
            //     if (_vars[i].has_lower) 
            //     {  
            //         if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(ceil(_vars[i].lower));
            //         _cur_assignment.push_back(_vars[i].lower);
            //     }
            //     else if (_vars[i].has_upper)
            //     {
            //         if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(floor(_vars[i].upper));
            //         _cur_assignment.push_back(_vars[i].upper);
            //     }
            //     else _cur_assignment.push_back(0);
            // }
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].is_constant) _cur_assignment.push_back(_vars[i].constant);
                else if (_vars[i].has_lower)
                {
                    // if (_vars[i].is_int) _cur_assignment.push_back(ceil(_vars[i].lower));
                    // else _cur_assignment.push_back(_vars[i].lower);
                    if (_vars[i].lower <= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_upper)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].upper >= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].lower);
                    }
                    else _cur_assignment.push_back(_vars[i].lower);
                }
                // else if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) 
                {
                    if (_vars[i].upper >= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_lower)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].lower <= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].upper);
                    }
                    else _cur_assignment.push_back(_vars[i].upper);
                    // if (_vars[i].is_int) _cur_assignment.push_back(floor(_vars[i].upper));
                    // else _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(0);
                // cout << _cur_assignment[i] << endl;
            }
        }
        else 
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].is_constant) _cur_assignment.push_back(_vars[i].constant);
                else if (_vars[i].has_lower)
                {
                    // if (_vars[i].is_int) _cur_assignment.push_back(ceil(_vars[i].lower));
                    // else _cur_assignment.push_back(_vars[i].lower);
                    if (_vars[i].lower <= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_upper)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].upper >= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].lower);
                    }
                    else _cur_assignment.push_back(_vars[i].lower);
                }
                // else if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) 
                {
                    if (_vars[i].upper >= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_lower)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].lower <= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].upper);
                    }
                    else _cur_assignment.push_back(_vars[i].upper);
                    // if (_vars[i].is_int) _cur_assignment.push_back(floor(_vars[i].upper));
                    // else _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(0);
                // cout << _cur_assignment[i] << endl;
            }
        }
        _unbounded_constraints.clear();
        _unsat_constraints.clear();
        for (int poly_pos = 0; poly_pos < _constraints.size(); poly_pos++)
        {
            pcon = & (_constraints[poly_pos]);
            mono_delta = 0;
            for (int mono_pos = 0; mono_pos < pcon->monomials.size(); mono_pos++)
            {
                mono_delta += pro_mono(pcon->monomials[mono_pos]);
            }
            pcon->value = mono_delta;
            init_pro_con_mix(pcon);
        }
        is_feasible = _unsat_constraints.empty();
        is_cur_feasible = _unsat_constraints.empty();
        // cout <<" init unsat size: "<< _unsat_constraints.size() << endl;
        //TODO:上下界初始化
        _object_weight = 0;
        if (is_feasible)
        {
            _object_weight = 1;
            _best_assignment = _cur_assignment;
            for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
            {
                obj_delta += pro_mono(_object_monoials[mono_pos]);
            }
            _best_object_value = obj_delta;
            mbd_emit();
        }
        // _object_weight = 0;
        // init score;
        // for (int bin_size = 0; bin_size < _bool_vars.size(); bin_size++)
        // {
        if (problem_type != 2) return;
        for (int var_pos : _bool_vars)
        {
            // var_pos = _bool_vars[bin_size];
            bin_var = & (_vars[var_pos]);
            // score = 0;
            // is_pos = (_cur_assignment[var_pos] > 0);
            for (int con_size : bin_var->constraints)
            {
                pcon =  & (_constraints[con_size]);
                pcon->p_bin_vars.push_back(var_pos);
            
            }
            // coeff_postive = pro_var_delta_in_obj(bin_var, var_pos, is_pos);
            // score += _object_weight * coeff_postive;
            // bin_var->obj_score = _object_weight * coeff_postive;
            // bin_var->bool_score = score;
        }
    }

    void qp_solver::init_pro_con_mix(polynomial_constraint * pcon)
    {
        Float value = pcon->value;
        Float bound = pcon->bound;
        int index = pcon->index;
        if (pcon->is_equal)
        {
            if (value >= bound - eb && value <= bound + eb)
            {
                _unsat_constraints.erase(index);
                pcon->is_sat = true;
            }
            else 
            {
                _unsat_constraints.insert(index);
                pcon->is_sat = false;
            }
        }
        else
        {
            if (pcon->is_less)
            {
                if (value <= bound + eb) 
                {
                    _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value < bound) _unbounded_constraints.insert(pcon->index);
                    else _unbounded_constraints.erase(index);
                }
                else 
                {
                    _unsat_constraints.insert(pcon->index);
                    pcon->is_sat = false;
                }
            }
            else 
            {
                if (value >= bound - eb) 
                {
                    _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value > bound) _unbounded_constraints.insert(pcon->index);
                    else _unbounded_constraints.erase(index);
                }
                else 
                {
                    _unsat_constraints.insert(pcon->index);
                    pcon->is_sat = false;
                }
            }
        }
        if (!pcon->is_sat)
        {
            int bin_var_num = _constraints[index].p_bin_vars.size();
            int real_var_num = _constraints[index].var_coeff.size() - _constraints[index].p_bin_vars.size();
            if (bin_var_num > 0) unsat_cls_num_with_bool++;
            else if (real_var_num > 0) unsat_cls_num_with_real++;
        }
        if (pcon->is_sat)
        {
            int bin_var_num = _constraints[index].p_bin_vars.size();
            int real_var_num = _constraints[index].var_coeff.size() - _constraints[index].p_bin_vars.size();
            if (bin_var_num > 0) unbounded_cls_num_with_bool++;
            else if (real_var_num > 0) unbounded_cls_num_with_real++;
        }
    }

    void qp_solver::pro_con_mix(polynomial_constraint * pcon)
    {
        Float value = pcon->value;
        Float bound = pcon->bound;
        int index = pcon->index;
        bool is_sat = pcon->is_sat;
        bool is_unbounded;
        if (_unbounded_constraints.find(index) != _unbounded_constraints.end()) is_unbounded = true;
        else is_unbounded = false;
        if (pcon->is_equal)
        {
            if (value >= bound - eb && value <= bound + eb)
            {
                if (!is_sat) _unsat_constraints.erase(index);
                pcon->is_sat = true;
            }
            else 
            {
                if (is_sat) _unsat_constraints.insert(index);
                pcon->is_sat = false;
            }
        }
        else
        {
            if (pcon->is_less)
            {
                if (value <= bound + eb) 
                {
                    if (!is_sat) _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value < bound) 
                    {
                        _unbounded_constraints.insert(pcon->index);
                    }
                    else _unbounded_constraints.erase(index);
                }
                else 
                {
                    if (is_sat) _unsat_constraints.insert(pcon->index);
                    pcon->is_sat = false;
                }
            }
            else 
            {
                if (value >= bound - eb) 
                {
                    if (!is_sat) _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value > bound) _unbounded_constraints.insert(pcon->index);
                    else _unbounded_constraints.erase(index);
                }
                else 
                {
                    if (is_sat) _unsat_constraints.insert(pcon->index);
                    pcon->is_sat = false;
                }
            }
        }
        int bin_var_num = _constraints[index].p_bin_vars.size();
        int real_var_num = _constraints[index].var_coeff.size() - _constraints[index].p_bin_vars.size();
        bool letter_unbounded;
        if (_unbounded_constraints.find(index) != _unbounded_constraints.end()) letter_unbounded = true;
        else letter_unbounded = false;
        if (is_sat && !pcon->is_sat)
        {
            if (bin_var_num > 0) unsat_cls_num_with_bool++;
            else if (real_var_num > 0) unsat_cls_num_with_real++;
        }
        else if (!is_sat && pcon->is_sat)
        {
            if (bin_var_num > 0) unsat_cls_num_with_bool--;
            else if (real_var_num > 0) unsat_cls_num_with_real--;
        }
        if (is_unbounded && !letter_unbounded)
        {
            if (bin_var_num > 0) unbounded_cls_num_with_bool++;
            else if (real_var_num > 0) unbounded_cls_num_with_real++;
        }
        else if (!is_unbounded && letter_unbounded)
        {
            if (bin_var_num > 0) unbounded_cls_num_with_bool--;
            else if (real_var_num > 0) unbounded_cls_num_with_real--;
        }
    }

    void qp_solver::random_walk_unsat_mix_not_dis()
    {
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        unordered_set<int> rand_unsat_idx;
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_vars.clear();
        _operation_value.clear();
        _operation_cons_pos.clear();  // 清空约束位置映射
        // int real_rand_num = 20;
        for (int i = 0; i < rand_num; i++) 
        {
            unordered_set<int>::iterator it(_unsat_constraints.begin());
            std::advance(it, rand() % _unsat_constraints.size());
            rand_unsat_idx.insert(*it);
        }
        // cout << rand_unsat_idx.size() << endl;
        for (int unsat_pos : rand_unsat_idx)
        {
            unsat_con = & (_constraints[unsat_pos]);
            delta = unsat_con->bound - unsat_con->value;
            for (auto var_coeff : unsat_con->var_coeff)
            {
                var_idx = var_coeff.first;
                a_coeff = & (var_coeff.second);
                // insert_var_change_value_bin(var_idx, a_coeff, delta, unsat_con);
                if (_vars[var_idx].is_bin) insert_var_change_value_bin(var_idx, a_coeff, 0, unsat_con, true);
                else if (!_vars[var_idx].is_bin) insert_var_change_value(var_idx, a_coeff, delta, unsat_con, true);
            }
        }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            _operation_cons_pos.push_back(-1);  // 对于 _operation_vars_sub 中的操作，使用 -1 表示没有约束关联
        }
        // for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") cout << " ??????";
        // }
        // cout << _operation_value.size() << endl;
        int var_pos;
        Float change_value, score;
        select_best_operation_mix(var_pos, change_value, score);
        if (score != INT32_MIN) execute_critical_move_mix(var_pos, change_value);
        else no_operation_walk_unsat();
    }

    void qp_solver::insert_operation_unsat_mix_not_dis()
    {
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();  // 清空约束位置映射
        for (int unsat_pos : _unsat_constraints)
        {
            unsat_con = & (_constraints[unsat_pos]);
            delta = unsat_con->bound - unsat_con->value; //想一下这个对不对
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
            // cout << "here " << endl;
            // cout << "varsub: " << _operation_vars_sub[i] << "value sub: " <<  _operation_value_sub[i] << endl;
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            _operation_cons_pos.push_back(-1);  // 对于 _operation_vars_sub 中的操作，使用 -1 表示没有约束关联
        }
        // for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     cout << "var: " << _vars[_operation_vars[i]].name << "value: " <<  _operation_value[i] << endl;
        // }
        // cout <<_operation_vars.size() << endl;
    }

    void qp_solver::insert_operation_sat_mix_not_dis()
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
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();  // 清空约束位置映射
        _obj_vars_in_unbounded_constraint.clear();//TODO:改成两个
        _obj_bin_vars_in_unbounded_constraint.clear();//TODO:改成两个
        for (int var_pos : _vars_in_obj)
        {
            obj_var = & (_vars[var_pos]);
            cur_value = _cur_assignment[var_pos];
            // if (_vars[var_pos].name == "y") continue;
            if (_vars[var_pos].is_bin)
            {
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
                if (linear_coeff_value == 0) continue;
                if (linear_coeff_value > 0 && cur_value == 0) continue;
                if (linear_coeff_value < 0 && cur_value == 1) continue;
                // 这里再好好想想，是不是要维护可满足性质呢？
                //TODO:采样目标函数，要不太大了，目标函数感觉要用CY学姐的
                for (int con_pos: obj_var->constraints)
                {
                    unbound_con = & (_constraints[con_pos]);
                    a_coeff = &(unbound_con->var_coeff[var_pos]);
                    if (a_coeff->obj_quadratic_coeff != 0 || a_coeff->obj_linear_coeff.size() != 0 || _unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        // unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
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
                for (int con_pos: obj_var->constraints)
                {
                    if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (unbound_con->is_equal) continue;
                        delta = unbound_con->bound - unbound_con->value;
                        a_coeff = &(unbound_con->var_coeff[var_pos]);
                        insert_var_change_value_sat(var_pos, a_coeff, delta, unbound_con, symflag, best_value, false);
                        _obj_vars_in_unbounded_constraint.insert(var_pos);
                    }
                }
                op_num = _operation_vars.size() - op_num;
                if (op_num == 0 && symflag == 1)
                // if (symflag == 1)
                {
                    if (_vars[var_pos].is_int) best_value = round(best_value);
                    best_value = best_value - _cur_assignment[var_pos];
                    if (check_var_shift(var_pos, best_value, false))
                    {
                        _operation_vars.push_back(var_pos);
                        _operation_value.push_back(best_value);
                        _operation_cons_pos.push_back(-1);  // 没有约束关联
                    }
                    _obj_vars_in_unbounded_constraint.insert(var_pos);
                }
            }
        }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            _operation_cons_pos.push_back(-1);  // 对于 _operation_vars_sub 中的操作，使用 -1 表示没有约束关联
        }
        // for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") cout << " ??????";
        // }
    }

    void qp_solver::random_walk_sat_mix_not_dis()
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
        unordered_set<int> rand_obj_idx;
        _operation_vars.clear();
        _operation_value.clear();
        _operation_vars_sub.clear();
        _operation_value_sub.clear();
        _operation_cons_pos.clear();  // 清空约束位置映射
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
            if (_vars[var_pos].name == "y") continue;
            if (!_vars[var_pos].is_bin) 
            {
                // if (_vars[var_pos].name =="b1") cout << ".....";
                op_num = _operation_vars.size();
                obj_var = & (_vars[var_pos]);
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
                for (int con_pos: obj_var->constraints)
                {
                    if (_unbounded_constraints.find(con_pos) != _unbounded_constraints.end())
                    {
                        unbound_con = & (_constraints[con_pos]);//考虑有没有目标函数里的变量
                        if (unbound_con->is_equal) continue;
                        delta = unbound_con->bound - unbound_con->value;
                        a_coeff = &(unbound_con->var_coeff[var_pos]);
                        insert_var_change_value_sat(var_pos, a_coeff, delta, unbound_con, symflag, best_value, true);
                    }
                }
                op_num = _operation_vars.size() - op_num;
                if (op_num == 0 && symflag == 1)
                // if (symflag == 1)
                {
                    if (_vars[var_pos].is_int) best_value = round(best_value);
                    best_value = best_value - _cur_assignment[var_pos];
                    if (check_var_shift(var_pos, best_value, true))
                    {
                        _operation_vars.push_back(var_pos);
                        _operation_value.push_back(best_value);
                        _operation_cons_pos.push_back(-1);  // 没有约束关联
                    }
                }
            }
            else if (_vars[var_pos].is_bin)
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
            }
            // for (int i = 0; i < _operation_vars.size(); i++)
            // {
            //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") 
            //     {
            //         // exit(0);
            //         cout << "name is :" << _vars[var_pos].name << endl;
            //         exit(0);
            //     }
                
            // }
        }
        // for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") cout << "^^^";
        // }
        for (int i = 0; i < _operation_vars_sub.size(); i++)
        {
            // if (_operation_value_sub[i] != 1 && _operation_value_sub[i] != -1) cout <<"??????" <<endl;
            _operation_vars.push_back(_operation_vars_sub[i]);
            _operation_value.push_back(_operation_value_sub[i]);
            _operation_cons_pos.push_back(-1);  // 对于 _operation_vars_sub 中的操作，使用 -1 表示没有约束关联
        }
        //  for (int i = 0; i < _operation_vars.size(); i++)
        // {
        //     if (_operation_value[i] == 2 && _vars[_operation_vars[i]].name =="b1") cout << " ??????";
        // }
        int var_pos;
        Float change_value_2, score;
        select_best_operation_mix(var_pos, change_value_2, score);
        if (score != INT32_MIN) execute_critical_move_mix(var_pos, change_value_2);
        else no_operation_walk_sat(no_operation_var);
        
    }

    void qp_solver::select_best_operation_mix(int & var_pos, Float & change_value, Float & score)
    {
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars.size();
        // 仅在开启tabu时检查并使用_cons_pos
        if (_constraint_tabu_enabled)
        {
            // if (op_size != _operation_cons_pos.size())
            // {
            //     // 只在最后输出一次错误信息
            //     static bool error_reported = false;
            //     if (!error_reported) {
            //         cout << "Error: _operation_vars.size() = " << op_size 
            //              << " != _operation_cons_pos.size() = " << _operation_cons_pos.size() << endl;
            //         error_reported = true;
            //     }
            //     return;
            // }
        }
        bool is_bms;
        // bms = 200;
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
        int rand_index, cons_pos = -1, cur_cons_pos = -1;
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars[rand_index];
                cur_shift = _operation_value[rand_index];
                if (_constraint_tabu_enabled) cur_cons_pos = _operation_cons_pos[rand_index];
                _operation_vars[rand_index] = _operation_vars[op_size - i - 1];
                _operation_value[rand_index] = _operation_value[op_size - i - 1];
                if (_constraint_tabu_enabled) _operation_cons_pos[rand_index] = _operation_cons_pos[op_size - i - 1];
            } 
            else {
                cur_var = _operation_vars[i];
                cur_shift = _operation_value[i];
                if (_constraint_tabu_enabled) cur_cons_pos = _operation_cons_pos[i];
            }
            if (is_cur_feasible)//打破faclay80,35的记录，cruoil02的记录，以及
            // if (true) //打破ring的两个记录 ,e-12是最后一个，e的-9是第二个
            // if (is_feasible) // 打破4个faclay记录的版本
                cur_score = calculate_score_cy_mix(cur_var, cur_shift);
            else 
                cur_score = calculate_score_mix(cur_var, cur_shift);
                // cur_score = calculate_score(cur_var, cur_shift);
            // var * cur_var_real = &(_vars[cur_var]);
            // if (cur_var_real->recent_value->contains(_cur_assignment[cur_var] + cur_shift) && !is_cur_feasible) 
            // {
            //     if (cur_score > 0)
            //         cur_score /= 1.5;
            //     else cur_score *= 1.5;
            // }
            if (cur_score > score) {
                score = cur_score;
                var_pos = cur_var;
                change_value = cur_shift;
                cons_pos = cur_cons_pos;
                // cout << change_value <<" ";
            }
        }
        if (cons_pos != -1 && _constraint_tabu_enabled)
        {
            _constraints[cons_pos].tabu_step = _steps + rand() % 10 + 3;
        }
    }

    void qp_solver::select_best_operation_lift(int & var_pos, Float & change_value, Float & score)
    {
        score = INT32_MIN;
        int cnt;
        int op_size = _operation_vars.size();
        bool is_bms;
        bms = 200;
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
        int best_lift_var = -1; 
        Float best_lift_shift, best_lift_score = INT32_MIN;
        int rand_index;
        for (int i = 0; i < cnt; i++) 
        {
            if (is_bms) 
            {
                rand_index = rand() % (op_size - i);
                cur_var = _operation_vars[rand_index];
                cur_shift = _operation_value[rand_index];
                _operation_vars[rand_index] = _operation_vars[op_size - i - 1];
                _operation_value[rand_index] = _operation_value[op_size - i - 1];
            } 
            else {
                cur_var = _operation_vars[i];
                cur_shift = _operation_value[i];
            }
            Float cons_lift = is_lift(cur_var, cur_shift);
            if (cons_lift == 0)
            {
                Float cur_lift_score =  cons_lift + obj_lift(cur_var, cur_shift);
                if (cur_lift_score > best_lift_score) {
                    best_lift_score > cur_lift_score;
                    best_lift_var = cur_var;
                    best_lift_shift = cur_shift;
                }
            }
            else 
            {
                cur_score = cons_lift + obj_lift(cur_var, cur_shift);
                // cur_score = obj_lift(cur_var, cur_shift);
                if (cur_score > score) {
                    score = cur_score;
                    var_pos = cur_var;
                    change_value = cur_shift;
                    // cout << change_value <<" ";
                }
            }
        }
        if (best_lift_var != -1)
        {
            score = best_lift_score;
            var_pos = best_lift_var;
            change_value = best_lift_shift;
        }
    }

    Float qp_solver::is_lift(int var_pos, Float change_value)
    {
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        Float state;
        var * nor_var;
        nor_var = & (_vars[var_pos]);
        for (int con_size : nor_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_value_delta(nor_var, pcon, var_pos, old_value, old_value + change_value);
            con_delta = pcon->value + var_delta;
            state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);//这里好像没有用mix
            score += pcon->weight * state;
        }
        return score;
    }
    
    Float qp_solver::obj_lift(int var_pos, Float change_value)
    {
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        Float state;
        var * nor_var;
        nor_var = & (_vars[var_pos]);
        return _object_weight * pro_var_value_delta_in_obj_cy(nor_var, var_pos, old_value, old_value + change_value);
    }

    Float qp_solver::judge_cons_state_mix(polynomial_constraint * pcon, Float var_delta, Float con_delta)
    {
        // Float bound = pcon->bound;
        // if (pcon->is_equal)
        // {
        //     if (fabs(bound - (var_delta + pcon->value)) < fabs(bound - pcon->value)) return 1;
        //     else return -1;
        // }
        // int more_flag;
        // if (var_delta > 0) more_flag = 1;
        // else if (var_delta < 0) more_flag = -1;
        // else more_flag = 0; 
        // // int state;
        // // if (pcon->is_less) state = con_delta <= bound ? 1 : 0;
        // // else state = con_delta >= bound ? 1 : 0;
        // // if (pcon->is_sat) state--;
        // // return state;
        // if (pcon->is_sat)
        // {
        //     if (pcon->is_less)
        //     {
        //         if (con_delta <= bound + eb) return 0;
        //         else return -1;
        //     }
        //     else 
        //     {
        //         if (con_delta >= bound - eb) return 0;
        //         else return -1;
        //     }
        // }
        // else
        // {
        //     if (pcon->is_less)
        //     {
        //         if (con_delta <= bound + eb) return 1;
        //         else return (- more_flag);
        //     }
        //     else 
        //     {
        //         if (con_delta >= bound - eb) return 1;
        //         else return more_flag;
        //     }
        // }

        // Float bound = pcon->bound;
        // int state;
        // if (pcon->is_equal) 
        // {
        //     // if (fabs(pcon->value - pcon->bound) > fabs(con_delta - pcon->bound)) state = 1;
        //     if (con_delta >= bound - eb && con_delta <= bound + eb) state = 1;
        //     else state = 0;
        //     // if (fabs(con_delta - pcon->bound) <= eb) state = 1;
        //     // if (fabs(pcon->value - pcon->bound) > fabs(con_delta - pcon->bound)) state = 1;
        //     // else state = -1;
        //     // return state;
        //     // state == (con_delta == bound) ? 1 : 0;
        //     // state = 1;
        // }
        // else if (pcon->is_less) state = (con_delta <= bound + eb) ? 1 : 0;
        // else state = (con_delta >= bound - eb) ? 1 : 0;
        // if (pcon->is_sat) state--;
        // return state;

        Float bound = pcon->bound;
        Float state;
        bool is_post_sat;
        if (pcon->is_equal) 
        {
            is_post_sat = (con_delta >= bound - eb && con_delta <= bound + eb);
            if (pcon->is_sat && !is_post_sat) state = -1;
            else if (!pcon->is_sat && is_post_sat) state = 1;
            else if (fabs(pcon->value - pcon->bound) > fabs(con_delta - pcon->bound)) state = 0.5;
            else if (fabs(pcon->value - pcon->bound) < fabs(con_delta - pcon->bound)) state = -0.5;
            else state = 0;
            // state *= 2;
        }
        else if (pcon->is_less) 
        {
            is_post_sat = (con_delta <= bound + eb);
            if (pcon->is_sat && !is_post_sat) state = -1;
            else if (!pcon->is_sat && is_post_sat) state = 1;
            else if (!pcon->is_sat && !is_post_sat)
            {
                if (con_delta > pcon->value) state = -0.5;
                else if (con_delta < pcon->value) state = 0.5;
            }
            else state = 0;
        }
        else 
        {
            is_post_sat = (con_delta >= bound - eb); //这里变成+eb反而1000+的一些例子效果会好
            if (pcon->is_sat && !is_post_sat) state = -1;
            else if (!pcon->is_sat && is_post_sat) state = 1;
            else if (!pcon->is_sat && !is_post_sat)
            {
                if (con_delta < pcon->value) state = -0.5;
                else if (con_delta > pcon->value) state = 0.5;
            }
            else state = 0;
        }
        // if (state == -0.5 || state == 0.5) state *= 2;
        return state;
    }

    Float qp_solver::judge_cons_state_bin_cy_mix(polynomial_constraint * pcon, Float var_delta, Float con_delta)
    {
        //chcek here check 从init开始全部的逻辑对不对，在LS里写一个BUGchecker
        //check 普通的算分逻辑
        //例子逻辑和这个check一下
        //等号的逻辑是不是哪里没处理好，不只是算分
        Float bound = pcon->bound;
        if (pcon->is_equal) 
        {
            if (var_delta + pcon->value >= bound -eb || var_delta + pcon->value <= bound + eb) return 0;
            else return - fabs(bound - (var_delta + pcon->value)) + fabs(bound - pcon->value);
        }
        int more_flag;
        if (var_delta > 0) more_flag = 1;
        else if (var_delta < 0) more_flag = -1;
        else more_flag = 0; 
        // eb = 0;
        if (pcon->is_sat)
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound + eb) return 0;
                else return (bound + eb - con_delta);
            }
            else 
            {
                if (con_delta >= bound - eb) return 0;
                else return (con_delta - (bound - eb));
            }
        }
        else
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound + eb) return (pcon->value - (pcon->bound + eb));
                else return (- var_delta);
            }
            else 
            {
                if (con_delta >= bound - eb) return ((pcon->bound - eb) - pcon->value);
                else return var_delta;
            }
        }
    }

    Float qp_solver::calculate_score_cy_mix(int var_pos, Float change_value)
    {
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        Float state;
        var * nor_var;
        nor_var = & (_vars[var_pos]);
        for (int con_size : nor_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_value_delta(nor_var, pcon, var_pos, old_value, old_value + change_value);
            con_delta = pcon->value + var_delta;
            state = judge_cons_state_bin_cy_mix(pcon, var_delta, con_delta);//这里好像没有用mix
            score += pcon->weight * state;
        }
        // score = 0;
        // score *= 100000;
        // return score;
        score -= _object_weight * pro_var_value_delta_in_obj_cy(nor_var, var_pos, old_value, old_value + change_value);
        return score;
    }

    Float qp_solver::calculate_score_mix(int var_pos, Float change_value)
    {
        Float score = 0;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        Float state;
        var * nor_var;
        nor_var = & (_vars[var_pos]);
        for (int con_size : nor_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_value_delta(nor_var, pcon, var_pos, old_value, old_value + change_value);
            con_delta = pcon->value + var_delta;
            // state = judge_cons_state_bin(pcon, var_delta, con_delta);
            state = judge_cons_state_mix(pcon, var_delta,con_delta);
            score += pcon->weight * state;
        }
        // score *= 1000;
        score -= _object_weight * pro_var_value_delta_in_obj(nor_var, var_pos, old_value, old_value + change_value);
        // score -= 1 * pro_var_value_delta_in_obj_cy(nor_var, var_pos, old_value, old_value + change_value);
        
        // b的变量和实数变量区分一下，先选哪个呢？打分也区分一下？先选哪个呢
        // 优化的部分
        // 打分的时候改一下sat->sat 和unsat -> unsat的
        // 分析具体的例子
        //看b的插入逻辑，看优化的逻辑
        return score;//把score这里改一下，改成bin的score，以及check pro_var_value有没有bug
    }

    void qp_solver::execute_critical_move_mix(int var_pos, Float change_value)
    {
        // change the value of cons, sat state
        // change the is_cur_feasible
        // change the tabu of var
        // change the cur_value
#ifdef OUTPUT_PROCESS
        cout << " 变量名字: "  << _vars[var_pos].name << " change_value: " << change_value << endl;
        // for (auto c : _unbounded_constraints) print_cons(c) << endl;
#endif
        // cout << _steps << " var pos: "  << _vars[var_pos].name << "change_value: "<< std::scientific << change_value << endl;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        // if (_vars[var_pos].is_bin && (_cur_assignment[var_pos] + change_value != 0) && (_cur_assignment[var_pos] + change_value != 1)) return; 
        Float mono_delta = 0;
        var * nor_var;
        var * bin_var;
        int bin_pos;
        int state;
        bool is_pos;
        int cur_score;
        _cur_assignment[var_pos] += change_value;
        nor_var = & (_vars[var_pos]);
        nor_var->recent_value->update(_cur_assignment[var_pos]);
        for (int con_size : nor_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            // var_delta = pro_var_value_delta(nor_var, pcon, var_pos, old_value, old_value + change_value);
            // pcon->value += var_delta;
            mono_delta = 0;
            for (int mono_pos = 0; mono_pos < pcon->monomials.size(); mono_pos++)
            {
                mono_delta += pro_mono(pcon->monomials[mono_pos]);
            }
            pcon->value = mono_delta;
            pro_con_mix(pcon);
        }
        if (change_value < 0) _vars[var_pos].last_pos_step = _steps + rand() % 10 + 3;
        else _vars[var_pos].last_neg_step = _steps + rand() % 10 + 3;
        is_cur_feasible = _unsat_constraints.empty();
        if (is_cur_feasible && !is_feasible)
        {
            _object_weight = 1;
            is_feasible = true;
        } 
        if (is_cur_feasible) update_best_solution();
    }

    void qp_solver::local_search_mix_not_dis()
    {
        cout << "mix " << endl;
        // initialize_mix();
        sta_cons();
        restart_by_new_solution();//test
        int var_pos;
        int bin_var_pos;
        Float bin_score, score;
        Float change_value, bin_change_value;
        bool mode;// 0 means bool, 1 means real;
        // sta_cons();
        for (_steps = 0; _steps <= _max_steps; _steps++)
        {
            //TODO
            if (_steps % 1000 == 0 && (TimeElapsed() > _cut_off)) break;
#ifdef OUTPUT_PROCESS
            // cout << " var pos: "  << var_pos << "change_value: " << change_value << endl;
            cout << "第" << _steps << "次迭代                                    " << endl;
            cout <<" unsat size: "<< _unsat_constraints.size() << endl;
            if (_unsat_constraints.size() < 5)
                for (auto index : _unsat_constraints)
                {
                    cout << " 约束名字 " <<  _constraints[index].name << " 约束左值: " << _constraints[index].value << " 约束右值: " << _constraints[index].bound << endl;
                }
            //         // print_cons(index); 
            //         cout <<": "<< index <<" " ;
            // if (1) 
            // {   
            //     for (auto index : _unsat_constraints)
            //         // print_cons(index); 
            //         cout <<": "<< index <<" " ;
            // }
            // cout << endl;
#endif
            if (is_cur_feasible)
            {
                insert_operation_sat_mix_not_dis();
                select_best_operation_mix(var_pos, change_value, score);
                // select_best_operation_lift(var_pos, change_value, score);
                // cout << "sat :  ";
                if (score > 0) execute_critical_move_mix(var_pos, change_value);
                else 
                {
                    update_weight();
                    random_walk_sat_mix_not_dis();    
                } 
            }
            else 
            {
                insert_operation_unsat_mix_not_dis();
                select_best_operation_mix(var_pos, change_value, score);
                // cout << score << endl;
                // cout << "unsat :  ";
                if (score > 0) execute_critical_move_mix(var_pos, change_value);
                else 
                {
                    // if (!compensate_move())
#ifdef OUTPUT_PROCESS
                    cout << "随机步" << endl;
#endif
                    if (true)
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

    void qp_solver::restart_by_new_solution()
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
        //prove : 1.有零选零的变量是对的，这样scip省略的解是属于有零选零的变量的，这样不会破坏等式约束的可满足性。其它变量维持之前找到的最优解
        //如果没有找到可行解或者第一次就重启的话，init是空的，好像也可以
        //如果是完备找到可行解的情况下，需要传递一个最优解，然后和等式的解之间做交集。等式的解中的变量赋值优先考虑，然后再是可行解，这样能确保等式约束满足，并且是优化过的，之后再优化不等式
        //最开始传递的时候其实可以传递一个全部变量的初始解？或者如果慢的话就可行解？
        //把b变量作为bound值搞一下，可以同时作为约束和bound
        if (problem_type != 0)
        // if (true)
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_init_solution_map.find(i) != _init_solution_map.end())
                {
                    // cout << _vars[i].name <<" "<< _init_solution_map[i] << endl;
                    _cur_assignment.push_back(_init_solution_map[i]);
                }
                else if (_vars[i].is_constant) _cur_assignment.push_back(_vars[i].constant);
                if (_vars[i].has_lower && _vars[i].has_upper)
                {
                    Float average = (_vars[i].lower + _vars[i].upper) / 2;
                    if (_vars[i].is_int) average = round(average);
                    _cur_assignment.push_back(average);
                }
                else if (_vars[i].has_lower)
                {
                    // if (_vars[i].is_int) _cur_assignment.push_back(ceil(_vars[i].lower));
                    // else _cur_assignment.push_back(_vars[i].lower);
                    if (_vars[i].lower <= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_upper)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].upper >= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].lower);
                    }
                    else _cur_assignment.push_back(_vars[i].lower);
                }
                // else if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) 
                {
                    if (_vars[i].upper >= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_lower)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].lower <= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].upper);
                    }
                    else _cur_assignment.push_back(_vars[i].upper);
                    // if (_vars[i].is_int) _cur_assignment.push_back(floor(_vars[i].upper));
                    // else _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(0);
                // cout << _cur_assignment[i] << endl;
            }
        }
        else 
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_init_solution_map.find(i) != _init_solution_map.end())
                {
                    _cur_assignment.push_back(_init_solution_map[i]);
                }
                else if (_vars[i].is_constant) _cur_assignment.push_back(_vars[i].constant);
                else if (_vars[i].has_lower)
                {
                    // if (_vars[i].is_int) _cur_assignment.push_back(ceil(_vars[i].lower));
                    // else _cur_assignment.push_back(_vars[i].lower);
                    if (_vars[i].lower <= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_upper)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].upper >= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].lower);
                    }
                    else _cur_assignment.push_back(_vars[i].lower);
                }
                // else if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) 
                {
                    if (_vars[i].upper >= 0) 
                    {
                        // cout << "here";
                        if (!_vars[i].has_lower)
                            _cur_assignment.push_back(0);
                        else if (_vars[i].lower <= 0)
                            _cur_assignment.push_back(0);
                        else _cur_assignment.push_back(_vars[i].upper);
                    }
                    else _cur_assignment.push_back(_vars[i].upper);
                    // if (_vars[i].is_int) _cur_assignment.push_back(floor(_vars[i].upper));
                    // else _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(0);
                // cout << _cur_assignment[i] << endl;
            }
        }
        _unbounded_constraints.clear();
        _unsat_constraints.clear();
        for (int poly_pos = 0; poly_pos < _constraints.size(); poly_pos++)
        {
            pcon = & (_constraints[poly_pos]);
            mono_delta = 0;
            for (int mono_pos = 0; mono_pos < pcon->monomials.size(); mono_pos++)
            {
                mono_delta += pro_mono(pcon->monomials[mono_pos]);
            }
            pcon->value = mono_delta;
            init_pro_con_mix(pcon);
        }
        is_feasible = _unsat_constraints.empty();
        is_cur_feasible = _unsat_constraints.empty();
        // cout <<" init unsat size: "<< _unsat_constraints.size() << endl;
        // for (auto index : _unsat_constraints)
        // {
        //     cout << _constraints[index].value << " " << _constraints[index].bound<< endl;
        //     print_cons(index); 
        // }
        //TODO:上下界初始化
        _object_weight = 0;
        if (is_feasible)
        {
            _object_weight = 1;
            _best_assignment = _cur_assignment;
            for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
            {
                obj_delta += pro_mono(_object_monoials[mono_pos]);
            }
            _best_object_value = obj_delta;
            mbd_emit();
        }
        // _object_weight = 0;
        // init score;
        // for (int bin_size = 0; bin_size < _bool_vars.size(); bin_size++)
        // {
        // if (problem_type != 2) return;
        for (int var_pos : _bool_vars)
        {
            // var_pos = _bool_vars[bin_size];
            bin_var = & (_vars[var_pos]);
            // score = 0;
            // is_pos = (_cur_assignment[var_pos] > 0);
            for (int con_size : bin_var->constraints)
            {
                pcon =  & (_constraints[con_size]);
                pcon->p_bin_vars.push_back(var_pos);
                // cout << bin_var->name << " ?? " << pcon->name << endl;
            }
            // coeff_postive = pro_var_delta_in_obj(bin_var, var_pos, is_pos);
            // score += _object_weight * coeff_postive;
            // bin_var->obj_score = _object_weight * coeff_postive;
            // bin_var->bool_score = score;
        }
    }

}