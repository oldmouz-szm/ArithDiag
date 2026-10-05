#include "sol.h"
namespace solver
{

    void qp_solver::judge_problem()
    {
        int bool_size = _bool_vars.size();
        int var_size = _vars.size();
        int int_size = _int_vars.size();
        int real_size = var_size - int_size;
        if (bool_size > 0)
        {
            if (bool_size == var_size) problem_type = 0;
            else if (int_size != 0 && real_size != 0) problem_type = 1;
            else if (int_size == 0 && real_size !=0 ) problem_type = 2;
        }
        else 
        {
            if (int_size == var_size) problem_type = 3;
            else if (int_size != 0) problem_type = 4;
            else problem_type = 5;
        }
    }

    void qp_solver::local_search()
    {
        if (_constraints.size() <= 50) cons_num_type = 0;
        else cons_num_type = 1;
        _start_time = std::chrono::steady_clock::now();
        // cout << _int_vars.size() << " "  << _bool_vars.size() << endl;
        if (_vars.size() > _int_vars.size() && _int_vars.size() > 0) 
        {
            cons_num_type = 1;
            // local_search_mix_not_dis();
            local_search_mix_balance();
        }
        else if (_int_vars.size() > _bool_vars.size()) 
        {
            // local_search_with_real();
            cons_num_type = 1;
            // local_search_mix_not_dis();
            local_search_mix_balance();
        }    

        else if (_constraints.size() == 0) local_search_without_cons();
        else
        {
            judge_problem();
            if (is_cons_quadratic)
            {
                cout << "quad_cons" <<endl;
                local_search_bin();
            }
            else 
            {
                cout << "linear_cons" << endl;
                local_search_bin_new();
            }
        } 
        // if (_constraints.size() == 0) local_search_without_cons();
        // judge_problem();
        // if (problem_type == 0) local_search_bin();
        // else if (problem_type < 3) local_search_mix();
        // else local_search_with_real();
    }

    void qp_solver::pro_con(polynomial_constraint * pcon)
    {
        Float value = pcon->value;
        Float bound = pcon->bound;
        int index = pcon->index;
        bool is_sat = pcon->is_sat;
        if (pcon->is_equal)
        {
            if (value == bound)
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
                if (value <= bound) 
                {
                    if (!is_sat) _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value != bound) _unbounded_constraints.insert(pcon->index);
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
                if (value >= bound) 
                {
                    if (!is_sat) _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value != bound) _unbounded_constraints.insert(pcon->index);
                    else _unbounded_constraints.erase(index);
                }
                else 
                {
                    if (is_sat) _unsat_constraints.insert(pcon->index);
                    pcon->is_sat = false;
                }
            }
        }
    }

    double qp_solver::TimeElapsed()
    {
        std::chrono::steady_clock::time_point finish = std::chrono::steady_clock::now();
        std::chrono::duration<double> duration = finish - _start_time;
        return duration.count();
    }

    void qp_solver::no_operation_walk_sat(int var_idx)
    {
        //TODO:
        // return;
        Float rand_val = 1, rand_val_2 = -1;
        // if (rand() % 100000 < 50000)
        // {
        //     if (check_var_shift(var_idx,rand_val,true)) execute_critical_move(var_idx,rand_val);
        //     else if (check_var_shift(var_idx,rand_val_2,true)) execute_critical_move(var_idx,rand_val_2);
        // }
        // else 
        // {
        //     if (check_var_shift(var_idx,rand_val_2,true)) execute_critical_move(var_idx,rand_val_2);
        //     else if (check_var_shift(var_idx,rand_val,true)) execute_critical_move(var_idx,rand_val);
        // }
        if (_vars[var_idx].is_bin)
        {
            Float change_value;
            if (_cur_assignment[var_idx] == 0) change_value = 1;
            else change_value = -1;
            if (check_var_shift_bool(var_idx,change_value,true)) execute_critical_move_mix(var_idx,change_value);
            return;
        }
        if (rand() % 100000 < 50000)
        {
            // cout << _vars[var_idx].name <<endl;
            if (check_var_shift(var_idx,rand_val,true)) execute_critical_move_mix(var_idx,rand_val);
            else if (check_var_shift(var_idx,rand_val_2,true)) execute_critical_move_mix(var_idx,rand_val_2);
        }
        else 
        {
            //  cout << _vars[var_idx].name <<endl;
            if (check_var_shift(var_idx,rand_val_2,true)) execute_critical_move_mix(var_idx,rand_val_2);
            else if (check_var_shift(var_idx,rand_val,true)) execute_critical_move_mix(var_idx,rand_val);
        }
    }

    int qp_solver::pro_var_value_delta_in_obj(var * nor_var, int var_pos, Float old_value, Float new_value)
    {
        if (_vars_in_obj.find(var_pos) == _vars_in_obj.end()) return 0;
        Float coeff_value = 0;
        Float delta = 0;
        int li_var_idx;
        Float coeff;
        Float li_var_coeff;
        Float quad_coeff;
        Float change_value = new_value - old_value;
        int postive_value = (change_value < 0) ? 1 : -1;
        quad_coeff = nor_var->obj_quadratic_coeff;
        if (quad_coeff != 0) delta += quad_coeff * (change_value) * (old_value + new_value);
        for (int linear_pos = 0; linear_pos < nor_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = nor_var->obj_linear_coeff[linear_pos];
            li_var_coeff = nor_var->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += nor_var->obj_constant_coeff;
        delta += change_value * coeff_value; 
        // delta *= postive_value;
        if (delta > 0) return 1;
        else if (delta == 0) return 0;
        else return -1;
    }

    Float qp_solver::pro_var_value_delta_in_obj_cy(var * nor_var, int var_pos, Float old_value, Float new_value)
    {
        if (_vars_in_obj.find(var_pos) == _vars_in_obj.end()) return 0;
        Float coeff_value = 0;
        Float delta = 0;
        int li_var_idx;
        Float coeff;
        Float li_var_coeff;
        Float quad_coeff;
        Float change_value = new_value - old_value;
        int postive_value = (change_value < 0) ? 1 : -1;
        quad_coeff = nor_var->obj_quadratic_coeff;
        // if (quad_coeff != 0) delta += quad_coeff * (change_value) * (old_value + new_value);
        if (quad_coeff != 0) delta += quad_coeff * ((new_value * new_value) - (old_value * old_value));
        // if (quad_coeff * (change_value) * (old_value + new_value) != quad_coeff * ((new_value * new_value) - (old_value * old_value)))
        // {
        //     cout << quad_coeff <<"  "<< (change_value)<<"  " <<old_value <<"  "<< new_value<<endl;
        //      cout << quad_coeff * (change_value) * (old_value + new_value) << "  "  << quad_coeff * ((new_value * new_value) - (old_value * old_value)) << endl;
        // }
        // cout << quad_coeff * (change_value) * (old_value + new_value) << "  "  << quad_coeff * (new_value * new_value) - (old_value * old_value) << endl;
        for (int linear_pos = 0; linear_pos < nor_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = nor_var->obj_linear_coeff[linear_pos];
            li_var_coeff = nor_var->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += nor_var->obj_constant_coeff;
        delta += change_value * coeff_value; 
        // delta *= postive_value;
        return delta;
    }

    int qp_solver::judge_cons_state(polynomial_constraint * pcon, Float con_delta)
    {
        Float bound = pcon->bound;
        int state;
        if (pcon->is_equal) state == (con_delta == bound) ? 1 : 0;
        else if (pcon->is_less) state = (con_delta <= bound) ? 1 : 0;
        else state = (con_delta >= bound) ? 1 : 0;
        if (pcon->is_sat) state--;
        return state;
        // if (pcon->is_sat)
        // {
        //     if (pcon->is_less)
        //     {
        //         if (con_delta <= bound) return 0;
        //         else return -1;
        //     }
        //     else 
        //     {
        //         if (con_delta >= bound) return 0;
        //         else return -1;
        //     }
        // }
        // else
        // {
        //     if (pcon->is_less)
        //     {
        //         if (con_delta <= bound) return 1;
        //         else return 0;
        //     }
        //     else 
        //     {
        //         if (con_delta >= bound) return 1;
        //         else return 0;
        //     }
        // }
    }

    void qp_solver::no_operation_walk_unsat()
    {
        // return;
        polynomial_constraint * unsat_con;
        all_coeff * a_coeff;
        int var_idx;
        Float delta;
        unordered_set<int> rand_unsat_idx;
        unordered_set<int>::iterator unsat_cl_rand(_unsat_constraints.begin());
        Float change_value;
        std::advance(unsat_cl_rand, rand() % _unsat_constraints.size());
        unsat_con = & (_constraints[* unsat_cl_rand]);
        auto unsat_var_rand = unsat_con->var_coeff.begin();
        std::advance(unsat_var_rand, rand() % unsat_con->var_coeff.size());
        var_idx = unsat_var_rand->first;
        // if (_vars[var_idx].is_bin)
        // {
        //     if (_cur_assignment[var_idx] == 0) change_value = 1;
        //     else change_value = -1;
        //     if (check_var_shift_bool(var_idx,change_value,true)) execute_critical_move(var_idx,change_value);
        //     return;
        // }
        // if (_vars[var_idx].has_lower)
        // {
        //     if (_int_vars.find(var_idx)!=_int_vars.end()) change_value = (ceil(_vars[var_idx].lower));
        //     else change_value = (_vars[var_idx].lower);
        //     if (check_var_shift(var_idx,change_value,true)) execute_critical_move(var_idx,change_value);
        // }
        // else if (_vars[var_idx].has_upper)
        // {
        //     if (_int_vars.find(var_idx)!=_int_vars.end()) change_value = (floor(_vars[var_idx].upper));
        //     else change_value = (_vars[var_idx].upper);
        //     if (check_var_shift(var_idx,change_value,true)) execute_critical_move(var_idx,change_value);
        // }
        if (_vars[var_idx].is_bin)
        {
            if (_cur_assignment[var_idx] == 0) change_value = 1;
            else change_value = -1;
            if (check_var_shift_bool(var_idx,change_value,true)) execute_critical_move_mix(var_idx,change_value);
            return;
        }
        if (_vars[var_idx].has_lower)
        {
            //  cout << _vars[var_idx].name <<endl;
            if (_int_vars.find(var_idx)!=_int_vars.end()) change_value = (ceil(_vars[var_idx].lower));
            else change_value = (_vars[var_idx].lower);
            if (check_var_shift(var_idx,change_value,true)) execute_critical_move_mix(var_idx,change_value);
        }
        else if (_vars[var_idx].has_upper)
        {
            //  cout << _vars[var_idx].name <<endl;
            if (_int_vars.find(var_idx)!=_int_vars.end()) change_value = (floor(_vars[var_idx].upper));
            else change_value = (_vars[var_idx].upper);
            if (check_var_shift(var_idx,change_value,true)) execute_critical_move_mix(var_idx,change_value);
        }
        else 
        {
            no_operation_walk_sat(var_idx);
            // if (check_var_shift(var_idx,1,1)) execute_critical_move(var_idx,1);
            // if (check_var_shift(var_idx,-1,1)) execute_critical_move(var_idx,-1);
        }
    }

    Float qp_solver::pro_mono_inc(monomial mono, int var_pos)
    {
        Float coeff = mono.coeff;
        Float delta;
        if (mono.is_multilinear) 
        {
            // delta = (_cur_assignment[mono.m_vars[0]] == 0) ? 1 : -1; 
            // return coeff * delta;
            if (mono.m_vars[0] == var_pos) 
            {
                delta = (_cur_assignment[mono.m_vars[0]] == 0) ? 1 : -1; 
                return coeff * _cur_assignment[mono.m_vars[1]] * delta;
            }
            else 
            {
                delta = (_cur_assignment[mono.m_vars[1]] == 0) ? 1 : -1; 
                return coeff * _cur_assignment[mono.m_vars[0]] * delta;
            }
        }
        else 
        {
            delta = (_cur_assignment[mono.m_vars[0]] == 0) ? 1 : -1; 
            return coeff * delta;
            // if (mono.m_vars[0] == var_pos) 
            // {
            //     delta = (_cur_assignment[mono.m_vars[0]] == 0) ? 1 : -1; 
            //     return coeff * _cur_assignment[mono.m_vars[1]] * delta;
            // }
            // else 
            // {
            //     delta = (_cur_assignment[mono.m_vars[1]] == 0) ? 1 : -1; 
            //     return coeff * _cur_assignment[mono.m_vars[0]] * delta;
            // }
            // delta_1 = (_cur_assignment[mono.m_vars[0]] == 0) ? 1 : -1; 
            // delta_2 = (_cur_assignment[mono.m_vars[1]] == 0) ? 1 : -1; 
            // if (mono.is_multilinear) return coeff * _cur_assignment[mono.m_vars[0]] * _cur_assignment[mono.m_vars[1]];
            // else return coeff * _cur_assignment[mono.m_vars[0]] * _cur_assignment[mono.m_vars[0]];
        }
    }

    bool qp_solver::judge_bin_var_feasible(int var_idx, all_coeff * a_coeff, polynomial_constraint * pcon)
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
        if (linear_coeff_value == 0) return true;
        if (pcon->is_equal)
        {
            if (linear_coeff_value * change_value + pcon->value == pcon->bound) return true;
            else return false;
        }
        bool insert_flag = (linear_coeff_value < 0) ^ (_cur_assignment[var_idx] == 0);
        bool less = pcon->is_less;
        if (insert_flag)
        {
            if (less && (fabs(linear_coeff_value) + pcon->value <= pcon->bound)) return true;
            else if (!less) return true;
        }
        else 
        {
            //down
            if (!less && (pcon->value - fabs(linear_coeff_value) >= pcon->bound)) return true;
            else if (less) return true;
        }
        return false;
    }

    Float qp_solver::pro_var_delta_in_obj_cy(var * bin_var, int var_pos, bool is_pos)
    {
        Float coeff_value = 0;
        int li_var_idx;
        Float li_var_coeff;
        int postive_value = is_pos ? 1 : -1;//看一下这里float to bool 的转换对不对，1，-1全反了呀！！！！
        // if (bin_var->obj_quadratic_coeff != 0) cout << " bin var has quar exp error  " <<endl;
        // else 
        // {
        for (int linear_pos = 0; linear_pos < bin_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = bin_var->obj_linear_coeff[linear_pos];
            li_var_coeff = bin_var->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += bin_var->obj_constant_coeff;
        coeff_value += bin_var->obj_quadratic_coeff;
        // }
        coeff_value *= postive_value; 
        return coeff_value;
    }

    Float qp_solver::judge_cons_state_bin_cy(polynomial_constraint * pcon, Float var_delta, Float con_delta)
    {
        //chcek here check 从init开始全部的逻辑对不对，在LS里写一个BUGchecker
        //check 普通的算分逻辑
        //例子逻辑和这个check一下
        //等号的逻辑是不是哪里没处理好，不只是算分
        Float bound = pcon->bound;
        if (pcon->is_equal) return - fabs(bound - (var_delta + pcon->value)) + fabs(bound - pcon->value);
        int more_flag;
        if (var_delta > 0) more_flag = 1;
        else if (var_delta < 0) more_flag = -1;
        else more_flag = 0; 
        // eb = 0;
        if (pcon->is_sat)
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound) return 0;
                else return (bound - con_delta);
            }
            else 
            {
                if (con_delta >= bound) return 0;
                else return (con_delta - bound);
            }
        }
        else
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound) return (pcon->value - pcon->bound);
                else return (- var_delta);
            }
            else 
            {
                if (con_delta >= bound) return (pcon->bound - pcon->value);
                else return var_delta;
            }
        }
    }

    int qp_solver::judge_cons_state_bin(polynomial_constraint * pcon, Float var_delta, Float con_delta)
    {
        Float bound = pcon->bound;
        if (pcon->is_equal)
        {
            if (fabs(bound - (var_delta + pcon->value)) < fabs(bound - pcon->value)) return 1;
            else return -1;
        }
        int more_flag;
        if (var_delta > 0) more_flag = 1;
        else if (var_delta < 0) more_flag = -1;
        else more_flag = 0; 
        // int state;
        // if (pcon->is_less) state = con_delta <= bound ? 1 : 0;
        // else state = con_delta >= bound ? 1 : 0;
        // if (pcon->is_sat) state--;
        // return state;
        if (pcon->is_sat)
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound) return 0;
                else return -1;
            }
            else 
            {
                if (con_delta >= bound) return 0;
                else return -1;
            }
        }
        else
        {
            if (pcon->is_less)
            {
                if (con_delta <= bound) return 1;
                else return (- more_flag);
            }
            else 
            {
                if (con_delta >= bound) return 1;
                else return more_flag;
            }
        }
    }

    int qp_solver::pro_var_delta_in_obj(var * bin_var, int var_pos, bool is_pos)
    {
        Float coeff_value = 0;
        int li_var_idx;
        Float li_var_coeff;
        int postive_value = is_pos ? 1 : -1;
        // if (bin_var->obj_quadratic_coeff != 0) cout << " bin var has quar exp error  " <<endl;
        // else 
        // {
        for (int linear_pos = 0; linear_pos < bin_var->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = bin_var->obj_linear_coeff[linear_pos];
            li_var_coeff = bin_var->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += bin_var->obj_constant_coeff;
        coeff_value += bin_var->obj_quadratic_coeff;
        // }
        coeff_value *= postive_value; 
        if (coeff_value > 0) return 1;
        else if (coeff_value == 0) return 0;
        else return -1;
    }

    void qp_solver::init_pro_con(polynomial_constraint * pcon)
    {
        Float value = pcon->value;
        Float bound = pcon->bound;
        int index = pcon->index;
        if (pcon->is_equal)
        {
            if (value == bound)
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
                if (value <= bound) 
                {
                    _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value != bound) _unbounded_constraints.insert(pcon->index);
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
                if (value >= bound) 
                {
                    _unsat_constraints.erase(index);//TODO:判断有没有再删除
                    pcon->is_sat = true;
                    if (value != bound) _unbounded_constraints.insert(pcon->index);
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

    Float qp_solver::pro_mono(monomial mono)
    {
        Float coeff = mono.coeff;
        if (mono.is_linear) return coeff * _cur_assignment[mono.m_vars[0]];
        else
        {
            if (mono.is_multilinear) return coeff * _cur_assignment[mono.m_vars[0]] * _cur_assignment[mono.m_vars[1]];
            else return coeff * _cur_assignment[mono.m_vars[0]] * _cur_assignment[mono.m_vars[0]];
        }
    }

    Float qp_solver::pro_var_delta(var * qp_var, polynomial_constraint * pcon, int var_pos, bool is_pos)
    {
        // bool
        all_coeff * a_coeff;
        Float coeff_value = 0;
        int li_var_idx;
        Float li_var_coeff;
        a_coeff = & (pcon->var_coeff[var_pos]);
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += a_coeff->obj_constant_coeff;
        coeff_value += a_coeff->obj_quadratic_coeff;
        if (is_pos) coeff_value = - coeff_value;
        return coeff_value;
    }

    Float qp_solver::pro_var_value_delta(var * qp_var, polynomial_constraint * pcon, int var_pos, Float old_value, Float new_value)
    {
        all_coeff * a_coeff;
        Float coeff_value = 0;
        Float delta = 0;
        int li_var_idx;
        Float coeff;
        Float li_var_coeff;
        Float quad_coeff;
        Float change_value = new_value - old_value;
        a_coeff = & (pcon->var_coeff[var_pos]);
        quad_coeff = a_coeff->obj_quadratic_coeff;
        // if (quad_coeff != 0) delta += quad_coeff * (change_value) * (old_value + new_value);
        if (quad_coeff != 0) delta += quad_coeff * ((new_value * new_value) - (old_value * old_value));
        for (int linear_pos = 0; linear_pos < a_coeff->obj_linear_coeff.size(); linear_pos++)
        {
            li_var_idx = a_coeff->obj_linear_coeff[linear_pos];
            li_var_coeff = a_coeff->obj_linear_constant_coeff[linear_pos];
            coeff_value += _cur_assignment[li_var_idx] * li_var_coeff;
        }
        coeff_value += a_coeff->obj_constant_coeff;
        delta += change_value * coeff_value; 
        return delta;
    }

    void qp_solver::initialize()
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
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].has_lower && _vars[i].has_upper)
                {
                    Float average = (_vars[i].lower + _vars[i].upper) / 2;
                    if (_vars[i].is_int) average = round(average);
                    _cur_assignment.push_back(average);
                }
                if (_vars[i].has_lower) 
                {  
                    if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(ceil(_vars[i].lower));
                    _cur_assignment.push_back(_vars[i].lower);
                }
                else if (_vars[i].has_upper)
                {
                    if (_int_vars.find(i) != _int_vars.end()) _cur_assignment.push_back(floor(_vars[i].upper));
                    _cur_assignment.push_back(_vars[i].upper);
                }
                else _cur_assignment.push_back(0);
            }
        }
        else 
        {
            for (int i = 0; i < _var_num; i++)
            {
                if (_vars[i].has_lower) _cur_assignment.push_back(ceil(_vars[i].lower));
                else if (_vars[i].has_upper) _cur_assignment.push_back(floor(_vars[i].upper));
                else _cur_assignment.push_back(0);
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
            init_pro_con(pcon);
        }
        is_feasible = _unsat_constraints.empty();
        is_cur_feasible = _unsat_constraints.empty();
        // cout <<" init unsat size: "<< _unsat_constraints.size() << endl;
        //TODO:上下界初始化
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
        _object_weight = 0;
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

    void qp_solver::update_weight()
    {
        // return ;
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        var * nor_var;
        var * bin_var;
        int bin_pos;
        int state;
        bool is_pos;
        int cur_score;
        for (int unsat_cl : _unsat_constraints)
        {
            pcon = & (_constraints[unsat_cl]);
            // if (pcon->weight <= 600)
            pcon->weight++;
            // for (int bin_size = 0; bin_size < pcon->p_bin_vars.size(); bin_size++)
            // {
            //     bin_pos = pcon->p_bin_vars[bin_size];
            //     bin_var = & (_vars[bin_pos]);
            //     is_pos = (_cur_assignment[bin_pos] > 0);
            //     var_delta = pro_var_delta(bin_var, pcon, bin_pos, is_pos);
            //     con_delta = pcon->value + var_delta;
            //     state = judge_cons_state(pcon, con_delta);
            //     bin_var->bool_score += state;
            // }
        }
        if (!is_cons_quadratic) return;
        if (is_feasible)
        {
            Float obj_delta = 0;
            for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
            {
                obj_delta += pro_mono(_object_monoials[mono_pos]);
            }
            if (_best_object_value < obj_delta && is_cur_feasible)
            {
#ifdef DEBUG
                cout <<" _object_weight: "<< _object_weight << endl;
#endif
                _object_weight++;
                // for (int obj_var : _vars_in_obj)
                // {
                //     bin_var = &(_vars[obj_var]);
                //     is_pos = _cur_assignment[obj_var];
                //     if (bin_var->is_bin)
                //     {
                //         bin_var->bool_score += pro_var_delta_in_obj(bin_var, obj_var, is_pos);
                //     }
                // }
            }
        }
    }

    bool qp_solver::check_var_shift(int var_idx, Float & change_value, bool rand_flag)
    {
        // cout << change_value << " ";
        if (_vars[var_idx].equal_bound || _vars[var_idx].is_constant) return false;
        if (fabs(change_value) < 1e-15) return false;
        if (change_value != change_value) return false;
        if (change_value < -__DBL_MAX__  || change_value > __DBL_MAX__) return false;
        if (change_value == 0) return false;
        if (!rand_flag)
        {
            if ((change_value > 0 && _steps <= _vars[var_idx].last_pos_step) || (change_value < 0 && _steps <= _vars[var_idx].last_neg_step)) return false;
            // if (_vars[var_idx].recent_value->contains(_cur_assignment[var_idx] + change_value)) return false;
        }   
        Float post_val = _cur_assignment[var_idx] + change_value;
        
        // 检查整数变量约束
        if (_vars[var_idx].is_int)
        {
            if (post_val != round(post_val)) return false;
        }
        
        // if (_bool_vars.find(var_idx) != _bool_vars.end())
        // {
        //     if (post_val != 0 && post_val != 1) return false;
        // }
        if (change_value < 0)
        {
            // return !_vars[var_idx].has_lower || post_val >= _vars[var_idx].lower;
            if (_vars[var_idx].has_lower && post_val <= _vars[var_idx].lower)
                change_value = _vars[var_idx].lower - _cur_assignment[var_idx];
        }
        else 
        {
            // return !_vars[var_idx].has_upper || post_val <= _vars[var_idx].upper;
            if (_vars[var_idx].has_upper && post_val >= _vars[var_idx].upper)
                change_value = _vars[var_idx].upper - _cur_assignment[var_idx];
        }
        if (change_value == 0) return false;
        return true;
        bool lower_sat = !_vars[var_idx].has_lower || post_val >= _vars[var_idx].lower;
        bool upper_sat = !_vars[var_idx].has_upper || post_val <= _vars[var_idx].upper;
        return lower_sat && upper_sat;
    }

    bool qp_solver::check_var_shift(int var_idx, double & change_value, bool rand_flag)
    {
        if (_vars[var_idx].equal_bound || _vars[var_idx].is_constant) return false;
        if (fabs(change_value) < 1e-15) return false;
        if (change_value != change_value) return false;
        if (change_value < -__DBL_MAX__  || change_value > __DBL_MAX__) return false;
        if (change_value == 0) return false;
        if (!rand_flag)
        {
            if ((change_value > 0 && _steps <= _vars[var_idx].last_pos_step) || (change_value < 0 && _steps <= _vars[var_idx].last_neg_step)) return false;
            // if (_vars[var_idx].recent_value->contains(_cur_assignment[var_idx] + change_value)) return false;
        }   
        Float post_val = _cur_assignment[var_idx] + change_value;
        
        // 检查整数变量约束
        if (_vars[var_idx].is_int)
        {
            if (post_val != round(post_val)) return false;
        }
        
        // if (_bool_vars.find(var_idx) != _bool_vars.end())
        // {
        //     if (post_val != 0 && post_val != 1) return false;
        // }
        if (change_value < 0)
        {
            // return !_vars[var_idx].has_lower || post_val >= _vars[var_idx].lower;
            if (_vars[var_idx].has_lower && post_val <= _vars[var_idx].lower)
                change_value = _vars[var_idx].lower - _cur_assignment[var_idx];
        }
        else 
        {
            // return !_vars[var_idx].has_upper || post_val <= _vars[var_idx].upper;
            if (_vars[var_idx].has_upper && post_val >= _vars[var_idx].upper)
                change_value = _vars[var_idx].upper - _cur_assignment[var_idx];
        }
        if (change_value == 0) return false;
        return true;
        bool lower_sat = !_vars[var_idx].has_lower || post_val >= _vars[var_idx].lower;
        bool upper_sat = !_vars[var_idx].has_upper || post_val <= _vars[var_idx].upper;
        return lower_sat && upper_sat;
    }

    bool qp_solver::check_var_shift_bool(int var_idx, Float & change_value, bool rand_flag)
    {
        if (_vars[var_idx].equal_bound || _vars[var_idx].is_constant) return false;
        if (change_value == 0) return false;
        if (!rand_flag)
        // if (0)
        {
            if ((change_value > 0 && _steps <= _vars[var_idx].last_pos_step) || (change_value < 0 && _steps <= _vars[var_idx].last_neg_step)) return false;
        }   
        Float post_val = _cur_assignment[var_idx] + change_value;
        if (post_val != 1 && post_val != 0) return false;
        bool lower_sat = !_vars[var_idx].has_lower || post_val >= _vars[var_idx].lower;
        bool upper_sat = !_vars[var_idx].has_upper || post_val <= _vars[var_idx].upper;
        return lower_sat && upper_sat;
    }

    void qp_solver::execute_critical_move(int var_pos, Float change_value)
    {
        // change the value of cons, sat state
        // change the is_cur_feasible
        // change the tabu of var
        // change the cur_value
        // cout << " var pos: "  << _vars[var_pos].name << "change_value: " << change_value << endl;
#ifdef DEBUG
        cout << " var pos: "  << var_pos << "change_value: " << change_value << endl;
#endif
        polynomial_constraint * pcon;
        Float var_delta, con_delta;
        Float old_value = _cur_assignment[var_pos];
        // if (_vars[var_pos].is_bin && (_cur_assignment[var_pos] + change_value != 0) && (_cur_assignment[var_pos] + change_value != 1)) return; 
        var * nor_var;
        var * bin_var;
        int bin_pos;
        int state;
        bool is_pos;
        int cur_score;
        _cur_assignment[var_pos] += change_value;
        nor_var = & (_vars[var_pos]);
        for (int con_size : nor_var->constraints)
        {
            pcon = & (_constraints[con_size]);
            var_delta = pro_var_value_delta(nor_var, pcon, var_pos, old_value, old_value + change_value);
            pcon->value += var_delta;
            if(problem_type != 2) pro_con(pcon);
            else pro_con_mix(pcon);
            //change the bin score
            //TODO: 想如果这个约束里的变量是变化的change_value会有影响不
            // for (int bin_size = 0; bin_size < pcon->p_bin_vars.size(); bin_size++)
            // {
            //     bin_pos = pcon->p_bin_vars[bin_size];
            //     bin_var = & (_vars[bin_pos]);
            //     is_pos = (_cur_assignment[bin_pos] > 0);
            //     var_delta = pro_var_delta(bin_var, pcon, bin_pos, is_pos);
            //     con_delta = pcon->value + var_delta;
            //     //delete the former res
            //     cur_score = - bin_var->obj_score;
            //     cur_score -= bin_var->constraints_score[con_size]; 
            //     // + letter res
            //     state = judge_cons_state(pcon, con_delta);
            //     cur_score += pcon->weight * state;
            //     bin_var->constraints_score[con_size] = pcon->weight * state;
            //     state = pro_var_delta_in_obj(bin_var, bin_pos, is_pos);
            //     cur_score += _object_weight * state;
            //     bin_var->obj_score = _object_weight * state;
            //     bin_var->bool_score = cur_score;
            // }
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

    void qp_solver::update_best_solution()
    {
        //TODO: 增量式修改
        Float obj_delta = 0;
        for (int mono_pos = 0; mono_pos < _object_monoials.size(); mono_pos++)
        {
            obj_delta += pro_mono(_object_monoials[mono_pos]);
        }
        if (_best_object_value > obj_delta)
        {
            _best_object_value = obj_delta;
            _best_assignment = _cur_assignment;
            _best_steps = _steps;
            mbd_emit();
        }
    }
    
    void qp_solver::print_best_solution()
    {
        int index = 0;
        cout << endl;
        for (auto sol : _best_assignment)
        {
            // cout << "bound" << index << ": ";
            // if (sol != 0)
            if (_vars[index].name == "objconstant") 
                cout <<_vars[index].name << "     " << std::fixed << std::setprecision(15) << _obj_constant << endl;
            else 
                cout <<_vars[index].name << "     " << std::fixed << std::setprecision(15) << sol << endl;
            index++;
        }
    }
}