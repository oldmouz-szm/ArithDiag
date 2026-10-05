#include "sol.h"
namespace solver
{

    bool qp_solver::is_true_number(string str) 
    {
        for (char ch : str) {
            if (!isdigit(ch) && ch != '.' && ch != '-' && ch != 'e'  && ch != '+') {
                return false;
            }
        }
        return true;
    }

    bool qp_solver::isNumber(string str) 
    {
        for (char ch : str) {
            if (!isdigit(ch) && ch != '.') {
                return false;
            }
        }
        return true;
    }

    void qp_solver::split_string(std::string in_string, std::vector<std::string> &str_vec, std::string pattern = " ")
    {
        std::string::size_type pos;
        in_string += pattern;
        size_t size = in_string.size();
        for (size_t i = 0; i < size; i++)
        {
            pos = in_string.find(pattern, i);
            if (pos < size)
            {
                std::string s = in_string.substr(i, pos - i);
                if (s != "")
                    str_vec.push_back(s);
                i = pos + pattern.size() - 1;
            }
        }
    }

    Float qp_solver::pro_coeff(string s_coeff)
    {
        // std::cout<<s_coeff<<std::endl;
        return stold(s_coeff);
        size_t pos = s_coeff.find("e");
        if (pos != string::npos)
        {
            Float mul;//还是没想懂这里为什么这样会效果变差
            int exp;
            Float coeff = 1;
            if (pos != 0)  
                coeff = stold(s_coeff.substr(0, pos+1));
            exp = stoi(s_coeff.substr(pos + 1, s_coeff.size() - pos - 1));
            if (exp > 0) 
                mul = 10;
            else 
            {
                exp = -exp;
                mul = 0.1;
            }
            for (int i = 0; i < exp; i++)
                coeff *= mul;
            return coeff;
        }
        else return stold(s_coeff);
    }

    int qp_solver::register_var(string s_var)
    {
        if (s_var =="") cout <<"read error "<<endl;
        string var_name = s_var;
        int size = -1;
        //register var 变量是什么变量?
        if (_vars_map.count(var_name) == 0)
        {
            size = _vars.size();
            _vars_map[var_name] = size;
            var cur(size, var_name);
            _vars.push_back(cur);
        }
        else 
        {
            size = _vars_map[var_name];
        }
        return size;
        
    }

    void qp_solver::read(char * filename)
    {
        freopen(filename,"r",stdin);
        // std::ifstream file1(filename);
        string line;
        int stage = 0;
        bool is_min;
        while (getline(cin, line)) 
        // while (getline(file1, line)) 
        {
            if (line == "" || line.find("\\") != string::npos) continue;
            if (line == "Minimize") 
            {
                is_min = true;
                stage = 1;
            }
            else if (line == "Maximize") 
            {
                is_min = false;
                stage = 1;
            }
            else if (line == "Subject To") stage = 2;//区分是哪个约束
            else if (line == "Bounds") 
            {
                _cons_num = _constraints.size();
                stage = 3;
            }
            else if (line == "General" || line == "Generals") stage = 4;
            else if (line == "Binary" || line == "Binaries") stage = 5;
            else if (line == "End") return;
            //TODO:每次都需要检查吗？直接读下一行，而不是再判断一下
            if (stage == 1) read_obj(line);
            else if (stage == 2) read_cons(line); 
            else if (stage == 3) read_bounds(line);
            else if (stage == 4) read_int(line);
            else if (stage == 5) read_bin(line);
            // cout << stage << endl;
        }
        // cout << " read finished" << endl;
        fclose(stdin);
        // file1.close();
    }

    // void qp_solver::read_obj(string line)
    // {
    //     if (line == "Minimize" && line == "Maximize" || line == "") return ;
    //     vector<string> read_vec;
    //     split_string(line,read_vec);
    //     int stage = 0;
    //     bool pos = true;
    //     int size, size_2;
    //     string var_name_1, var_name_2;
    //     Float coeff;
    //     int quadratic_index;
    //     for (int i = 0; i < read_vec.size(); i++)
    //     {
    //         if (read_vec[i] == "obj:") continue;
    //         if (read_vec[i] == "[")
    //         {
    //             is_obj_quadratic = true;
    //             with_quadratic = true;
    //             i++;
    //             quadratic_index = i;
    //         }    
    //         else if (read_vec[i].find("]") != string::npos)
    //         {
    //             with_quadratic = false;
    //             i++;
    //             //TODO:  if /2 not , then * 2;
    //         }
    //         if (!with_quadratic)
    //         {
    //             if (i == 0 && read_vec[i] != "-" && read_vec[i] != "+")
    //             {
    //                 stage++;
    //                 pos = true;
    //             }
    //             if (stage == 0)
    //             {
    //                 if (read_vec[i] == "+") pos = true;
    //                 else pos = false;
    //                 stage++;
    //             }
    //             else if (stage == 1)
    //             {
    //                 if (!isdigit(read_vec[i][0]) && read_vec[i][0]!= '.')
    //                 {// + x
    //                     coeff = pos ? 1 : -1;
    //                     i--;
    //                 }
    //                 else 
    //                 {  
    //                     coeff = pro_coeff(read_vec[i]);
    //                     if (!pos) coeff = - coeff;
    //                 }
    //                 stage++;
    //             }
    //             else if (stage == 2)
    //             {
    //                 size = register_var(read_vec[i]);
    //                 if (coeff != 0) 
    //                 {
    //                     _vars[size].obj_constant_coeff += coeff;
    //                     _vars_in_obj.insert(size);
    //                 }
    //                 stage = 0;
    //             }
    //             else cout << " read_obj error: stage number exception ";
    //         }
    //         else 
    //         {
    //             if (i == quadratic_index && read_vec[i] != "-" && read_vec[i] != "+")
    //             {
    //                 stage++;
    //                 pos = true;
    //             }
    //             if (stage == 0)
    //             {
    //                 pos = read_vec[i] == "+" ? true : false;
    //                 stage++;
    //             }
    //             else if (stage == 1)
    //             {
    //                 if (!isdigit(read_vec[i][0]) && read_vec[i][0]!= '.')
    //                 {
    //                     coeff = pos ? 1 : -1;
    //                     i--;
    //                 }
    //                 else 
    //                 {
    //                     coeff = pro_coeff(read_vec[i]);
    //                     if (!pos) coeff = - coeff;
    //                 }
    //                 coeff /= 2; //2
    //                 stage++;
    //             }
    //             else if (stage == 2)
    //             {
    //                 if (read_vec[i].find('^') != string::npos)
    //                 {
    //                     size = register_var(read_vec[i].substr(0,read_vec.size()-2));
    //                     _vars[size].obj_quadratic_coeff += coeff;
    //                     _vars_in_obj.insert(size);
    //                 }
    //                 else 
    //                 {
    //                     var_name_1 = read_vec[i];
    //                     var_name_2 = read_vec[i+2];
    //                     size = register_var(var_name_1);
    //                     size_2 = register_var(var_name_2);
    //                     _vars[size].obj_linear_coeff.push_back(size_2);
    //                     _vars[size].obj_linear_constant_coeff.push_back(coeff);
    //                     _vars[size_2].obj_linear_coeff.push_back(size);
    //                     _vars[size_2].obj_linear_constant_coeff.push_back(coeff);
    //                     _vars_in_obj.insert(size);
    //                     _vars_in_obj.insert(size_2);
    //                     i+=2;
    //                 }
    //                 stage = 0;
    //             }
    //             else cout << " read_obj error: stage number exception ";
    //         }
    //     }
    // }
    // revised in 9.14
    
    void qp_solver::read_obj(string line)
    {    
        if (line == "Minimize" || line == "Maximize" || line == "") 
        {
            if (line == "Maximize") is_minimize = false;
            return ;
        }
        // cout << line << endl;
        vector<string> read_vec;
        split_string(line, read_vec);
        int stage = 0;
        bool pos = true;
        int size, size_2;
        string var_name_1, var_name_2;
        Float coeff;
        int quadratic_index = 0; //改成跟空格无关的判断，cons是不是也是这里有问题？
        for (int i = 0; i < read_vec.size(); i++)
        {
            if (read_vec[i] == "") 
            {
                quadratic_index++;
                continue;
            }
            if (read_vec[i] == "obj:") 
            {
                quadratic_index++;
                continue;
            }
            if (read_vec[i] == "[")
            {
                is_obj_quadratic = true;
                with_quadratic = true;
                i++;
                quadratic_index = i;
                if (i == read_vec.size()) return;
                stage = 0;
            }    
            else if (read_vec[i].find("]") != string::npos)
            {
                with_quadratic = false;
                i++;
                quadratic_index = i;
                stage = 0;
                pos = true;
                if (i == read_vec.size()) break;
                //TODO:  if /2 not , then * 2;
            }
            else if (read_vec[i] == "/2" || read_vec[i] == "/") break;
            if (i == quadratic_index && read_vec[i] != "-" && read_vec[i] != "+")
            {
                stage++;
                pos = true;
            }
            if (stage == 0)
            {
                pos = read_vec[i] == "+" ? true : false;
                stage++;
            }
            else if (stage == 1)
            {
                if (!isdigit(read_vec[i][0]) && read_vec[i][0]!= '.')
                {// + x
                    coeff = pos ? 1 : -1;
                    i--;
                    quadratic_index = -100;
                }
                else 
                {  
                    coeff = pro_coeff(read_vec[i]);
                    if (!pos) coeff = - coeff;
                }
                if (!is_minimize) coeff = - coeff;
                if (with_quadratic) coeff /= 2;
                stage++;
            }
            else if (stage == 2)
            {
                if (!with_quadratic)
                {
                    if (read_vec[i] != "objconstant")
                    {
                        size = register_var(read_vec[i]);
                        if (coeff != 0) 
                        {
                            _vars[size].obj_constant_coeff += coeff;
                            _vars[size].is_in_obj = true;
                            _vars_in_obj.insert(size);
                            //mono 
                            _vars[size].obj_monomials.push_back(_object_monoials.size());
                            monomial mono(size, coeff, true);
                            _object_monoials.push_back(mono);
                        }
                    }
                }
                else 
                {
                    if (read_vec[i].find('^') != string::npos)
                    {
                        size = register_var(read_vec[i].substr(0,read_vec[i].size()-2));
                        _vars[size].obj_quadratic_coeff += coeff;
                        _vars[size].is_in_obj = true;
                        _vars_in_obj.insert(size);
                        _vars[size].obj_monomials.push_back(_object_monoials.size());
                        monomial mono(size, coeff, false);
                        _object_monoials.push_back(mono);
                    }
                    else if ((i+1 <= read_vec.size() - 1) && read_vec[i+1] == "^2") //new
                    {
                        size = register_var(read_vec[i]);
                        _vars[size].obj_quadratic_coeff += coeff;
                        _vars[size].is_in_obj = true;
                        _vars_in_obj.insert(size);
                        _vars[size].obj_monomials.push_back(_object_monoials.size());
                        monomial mono(size, coeff, false);
                        _object_monoials.push_back(mono);
                        i++;
                    }
                    else 
                    {
                        var_name_1 = read_vec[i];
                        var_name_2 = read_vec[i+2];
                        size = register_var(var_name_1);
                        size_2 = register_var(var_name_2);
                        _vars[size].is_in_obj = true;
                        _vars[size_2].is_in_obj = true;
                        _vars[size].obj_linear_coeff.push_back(size_2); //TODO:这里应该用指针？
                        _vars[size].obj_linear_constant_coeff.push_back(coeff);
                        _vars[size_2].obj_linear_coeff.push_back(size);
                        _vars[size_2].obj_linear_constant_coeff.push_back(coeff);
                        _vars_in_obj.insert(size);
                        _vars_in_obj.insert(size_2);
                        i+=2;
                        //mono
                        _vars[size].obj_monomials.push_back(_object_monoials.size());
                        _vars[size_2].obj_monomials.push_back(_object_monoials.size());
                        monomial mono(size, size_2, coeff, false);
                        _object_monoials.push_back(mono);
                    }
                }
                stage = 0;
            }
            else 
            {
                cout << line << endl;
                cout << " read_obj error: stage number exception ";
                exit (0);
            }
        }
    }

    void qp_solver::read_cons(string line)
    {
        //想是在这里构建系数还是在initial那里，是要lazy构建还是on the fly
        // std::cout<<line<<endl;
        if (line == "Subject To" || line == "") return ;
        vector<string> read_vec;
        split_string(line, read_vec);
        int stage = 0;
        bool pos = true;
        int size, size_2;
        string var_name_1, var_name_2;
        Float coeff;
        int quadratic_index = 0;
        int name_pos;
        for (int i = 0; i < read_vec.size(); i++)
        {
            if (read_vec[i] == "") 
            {
                quadratic_index++;
                continue;
            }
            if (bound_flag)
            {
                bound_flag = false;
                // cout << read_vec[i] << endl;
                _constraints[_cons_num].bound = pro_coeff(read_vec[i]);
                avg_bound += fabs(_constraints[_cons_num].bound);
                break;
            }
            name_pos = read_vec[i].find(':');
            if (name_pos != string::npos) 
            {
                _cons_num++;
                polynomial_constraint con;
                con.index = _cons_num;
                con.name = read_vec[i].substr(0, name_pos);
                _constraints.push_back(con);
                quadratic_index++;
                continue;
            }
            if (read_vec.size() == 1 && isNumber(read_vec[0]))
            {
                _constraints[_cons_num].bound = pro_coeff(read_vec[0]);
                avg_bound += fabs(_constraints[_cons_num].bound);
                break;
            }//这里可以写的和下面那个bound_flag合并一下
            if (read_vec[i].find('=') != string::npos)
            {
                if (read_vec[i] == "=") _constraints[_cons_num].is_equal = true;
                else if (read_vec[i] == ">=") _constraints[_cons_num].is_less = false;
                if (i + 1 <= read_vec.size() - 1)
                    _constraints[_cons_num].bound = pro_coeff(read_vec[i+1]);
                // else bound_flag = true;
                avg_bound += fabs(_constraints[_cons_num].bound);
                break;
            }
            if (read_vec[i] == "[")
            {
                // is_obj_quadratic = true;
                is_cons_quadratic = true;
                with_quadratic = true;
                i++;
                quadratic_index = i;
                if (i == read_vec.size()) return;
                // cout << read_vec[i] << endl;
                // cout << quadratic_index <<endl;
                stage = 0;
            }    
            else if (read_vec[i].find("]") != string::npos)
            {
                with_quadratic = false;
                i++;
                if (i == read_vec.size()) break;//这里会出问题，如果不break的话，可能导致越界访问到错误的内存，然后下面的if就通过了比如0682和0681里面有相同的内容但是结果不一样。
                quadratic_index = i;
                stage = 0;
                pos = true;
                if (read_vec[i].find('=') != string::npos)
                {
                    if (i + 2 > read_vec.size() || read_vec[i + 1] == "") 
                    {
                        bound_flag = true;
                        if (read_vec[i] == "=") _constraints[_cons_num].is_equal = true;
                        else if (read_vec[i] == ">=") _constraints[_cons_num].is_less = false;
                        break;
                    }
                    if (read_vec[i] == "=") _constraints[_cons_num].is_equal = true;
                    else if (read_vec[i] == ">=") _constraints[_cons_num].is_less = false;
                    _constraints[_cons_num].bound = pro_coeff(read_vec[i+1]);
                    avg_bound += fabs(_constraints[_cons_num].bound);
                    break;
                }
            }
            if (i == quadratic_index && read_vec[i] != "-" && read_vec[i] != "+")
            {
                // cout << read_vec[i] << " ";
                stage++;
                pos = true;
                // cout << stage <<endl;
            }
            if (stage == 0)
            {
                // cout << read_vec[i] << " ";
                pos = read_vec[i] == "+" ? true : false;
                stage++;
                // cout <<stage <<endl;
            }
            else if (stage == 1)
            {
                // cout << read_vec[i] << " ";
                if (!isdigit(read_vec[i][0]) && read_vec[i][0]!= '.')
                {// + x
                    coeff = pos ? 1 : -1;
                    i--;
                    quadratic_index = -100;
                }
                else 
                {  
                    coeff = pro_coeff(read_vec[i]);
                    if (!pos) coeff = - coeff;
                }
                // cout << coeff << endl;
                stage++;
                // cout <<stage<<endl;
            }
            else if (stage == 2)
            {
                // cout << read_vec[i] << " ";
                if (!with_quadratic)
                {
                    size = register_var(read_vec[i]);
                    if (coeff != 0) 
                    {
                        _vars[size].constraints.insert(_cons_num);
                        monomial mono(size, coeff, true);
                        _constraints[_cons_num].monomials.push_back(mono);
                        //TODO: 构建变量的系数多项式
                        polynomial_constraint * cur_con = & (_constraints[_cons_num]);
                        auto coeff_pos = cur_con->var_coeff.find(size);
                        if (coeff_pos != cur_con->var_coeff.end()) coeff_pos->second.obj_constant_coeff += coeff; 
                        else 
                        {
                            all_coeff new_coeff;
                            new_coeff.obj_constant_coeff += coeff;
                            cur_con->var_coeff[size] = new_coeff;
                        }
                    }
                }
                else 
                {
                    _constraints[_cons_num].is_quadratic = true;
                    if (read_vec[i].find('^') != string::npos)
                    {
                        size = register_var(read_vec[i].substr(0,read_vec[i].size()-2));
                        _vars[size].constraints.insert(_cons_num);
                        monomial mono(size, coeff, false);
                        _constraints[_cons_num].monomials.push_back(mono);
                        //构建变量的系数多项式
                        polynomial_constraint * cur_con = & (_constraints[_cons_num]);
                        auto coeff_pos = cur_con->var_coeff.find(size);
                        if (coeff_pos != cur_con->var_coeff.end()) coeff_pos->second.obj_quadratic_coeff += coeff; 
                        else 
                        {
                            all_coeff new_coeff;
                            new_coeff.obj_quadratic_coeff += coeff;
                            cur_con->var_coeff[size] = new_coeff;
                        }
                    }
                    else if ((i+1 <= read_vec.size() - 1) && read_vec[i+1] == "^2") //new
                    {
                        size = register_var(read_vec[i]);
                        _vars[size].constraints.insert(_cons_num);
                        monomial mono(size, coeff, false);
                        _constraints[_cons_num].monomials.push_back(mono);
                        //构建变量的系数多项式
                        polynomial_constraint * cur_con = & (_constraints[_cons_num]);
                        auto coeff_pos = cur_con->var_coeff.find(size);
                        if (coeff_pos != cur_con->var_coeff.end()) coeff_pos->second.obj_quadratic_coeff += coeff; 
                        else 
                        {
                            all_coeff new_coeff;
                            new_coeff.obj_quadratic_coeff += coeff;
                            cur_con->var_coeff[size] = new_coeff;
                        }
                        i++;
                    }
                    else 
                    {
                        var_name_1 = read_vec[i];
                        var_name_2 = read_vec[i+2];
                        size = register_var(var_name_1);
                        size_2 = register_var(var_name_2);
                        _vars[size].constraints.insert(_cons_num);
                        _vars[size_2].constraints.insert(_cons_num);
                        monomial mono(size, size_2, coeff, false);
                        _constraints[_cons_num].monomials.push_back(mono);
                        i+=2;
                        //构建变量的系数多项式
                        polynomial_constraint * cur_con = & (_constraints[_cons_num]);
                        auto coeff_pos_1 = cur_con->var_coeff.find(size);
                        auto coeff_pos_2 = cur_con->var_coeff.find(size_2);
                        if (coeff_pos_1 != cur_con->var_coeff.end())
                        {
                            coeff_pos_1->second.obj_linear_constant_coeff.push_back(coeff);
                            coeff_pos_1->second.obj_linear_coeff.push_back(size_2);
                        } 
                        else 
                        {
                            all_coeff new_coeff;
                            new_coeff.obj_linear_constant_coeff.push_back(coeff);
                            new_coeff.obj_linear_coeff.push_back(size_2);
                            cur_con->var_coeff[size] = new_coeff;
                        }
                        if (coeff_pos_2 != cur_con->var_coeff.end())
                        {
                            coeff_pos_2->second.obj_linear_constant_coeff.push_back(coeff);
                            coeff_pos_2->second.obj_linear_coeff.push_back(size);
                        } 
                        else 
                        {
                            all_coeff new_coeff;
                            new_coeff.obj_linear_constant_coeff.push_back(coeff);
                            new_coeff.obj_linear_coeff.push_back(size);
                            cur_con->var_coeff[size_2] = new_coeff;
                        }
                    }
                }
                stage = 0;
                // cout <<stage <<endl;
            }
            // else cout <<"stage: "<< stage << " read_cons error: stage number exception ";
        }
    }

    void qp_solver::read_bounds(string line)
    {
        if (line == "Bounds" || line == "") return ;
        // cout << line <<endl;
        vector<string> read_vec;
        split_string(line, read_vec);
        // cout << read_vec.size() << endl;
        int size;
        if (read_vec.size() == 5)
        {
            size = register_var(read_vec[2]);
            if (read_vec[0] == "-inf" || read_vec[0] == "-infinity")
            {
                _vars[size].has_lower = false;
            }
            else 
            {
                _vars[size].has_lower = true;
                _vars[size].lower = pro_coeff(read_vec[0]);
            }
            if (read_vec[4] == "inf" || read_vec[0] == "infinity")
            {
                _vars[size].has_upper = false;
            }
            else 
            {
                _vars[size].has_upper = true;
                _vars[size].upper = pro_coeff(read_vec[4]);
            }
            if (_vars[size].upper == _vars[size].lower)
            {
                _vars[size].is_constant = true;
                _vars[size].constant = _vars[size].upper;
                _vars[size].equal_bound = true;
            }
            // cout << read_vec[4] << " "  << read_vec[0] << endl;
            // size = register_var(read_vec[2]);
            // _vars[size].has_lower = true;
            // _vars[size].has_upper = true;
            // _vars[size].upper = pro_coeff(read_vec[4]);
            // _vars[size].lower = pro_coeff(read_vec[0]);
            // if (_vars[size].upper == _vars[size].lower) _vars[size].equal_bound = true;
        }
        else if (read_vec[1] == "Free" || read_vec[1] == "free")
        {
            // cout << "here" << read_vec[0] << endl;
            size = register_var(read_vec[0]);
            _vars[size].has_lower = false;
            // std::cout << "here";
        }
        else if (read_vec[1] == "<=")
        {
            // cout << " here " << endl;
            if (!is_true_number(read_vec[0]))
            {
                // cout << " here1 " << endl;
                size = register_var(read_vec[0]);
                _vars[size].has_upper = true;
                _vars[size].upper = pro_coeff(read_vec[2]);
            }
            else 
            {
                // cout << " here2 " << endl;
                size = register_var(read_vec[2]);
                _vars[size].has_lower = true;
                _vars[size].lower = pro_coeff(read_vec[0]);
            }
        }
        else if (read_vec[1] == ">=")
        {
            if (!is_true_number(read_vec[0]))
            {
                size = register_var(read_vec[0]);
                _vars[size].has_lower = true;
                _vars[size].lower = pro_coeff(read_vec[2]);
            }
            else 
            {
                size = register_var(read_vec[2]);
                _vars[size].has_upper = true;
                _vars[size].upper = pro_coeff(read_vec[0]);
            }
        }
        else
        {
            size = register_var(read_vec[0]);
            if (read_vec[0] == "objconstant") 
            {
                _obj_constant = pro_coeff(read_vec[2]);
                // cout << _obj_constant << endl;
                _vars[size].is_constant = true;
            }
            else 
            {
                // cout << " constant = error : no processing ";
                _vars[size].is_constant = true;
                _vars[size].constant = pro_coeff(read_vec[2]);
            }
        }
    }

    void qp_solver::read_int(string line)
    {
        // cout << " int var : " << line << endl; 
        if (line == "General" || line =="Generals" || line == "") return ;
        vector<string> read_vec;
        split_string(line, read_vec);
        int size;
        for (int i = 0; i < read_vec.size(); i++)
        {
            if (read_vec[i] == "") continue;
            size = register_var(read_vec[i]);
            _vars[size].is_int = true;
            _int_vars.insert(size);
        }
    }
    
    void qp_solver::read_bin(string line)
    {
        // cout << " bin var : " << line << endl; 
        if (line == "Binary" || line == "Binaries"|| line == "") return ;
        vector<string> read_vec;
        split_string(line, read_vec);
        int size;
        for (int i = 0; i < read_vec.size(); i++)
        {
            if (read_vec[i] == "") continue;
            size = register_var(read_vec[i]);
            _vars[size].is_bin = true;
            _vars[size].is_int = true;
            _bool_vars.insert(size);
            _int_vars.insert(size);
        }
    }

    void qp_solver::print_formula()
    {
        int num = 0;
        if (is_minimize) cout << " minimize: " <<endl;
        else cout << " maximize: " << endl;
        for (auto mono : _object_monoials)
        {
            if (num != 0) cout << " + " ;
            print_mono(mono);
            num++;
        }
        if (_obj_constant != 0) cout << " " << _obj_constant;
        cout << endl;
        cout << "constraints: " << endl;
        for (auto cons : _constraints)
        {
            num = 0;
            cout << cons.name <<": ";
            for (auto mono : cons.monomials)
            {
                if (num != 0) cout << " + " ;
                print_mono(mono);
                num++;
            }
            if (cons.is_equal) cout << " = ";
            else if (cons.is_less) cout << " <= ";
            else cout << " >= ";
            cout << cons.bound;
            cout << endl;
        }
    }

    void qp_solver::print_cons(int cons_idx)
    {
        int num = 0;
        for (auto mono : _constraints[cons_idx].monomials)
        {
            if (num != 0) cout << " + " ;
            print_mono(mono);
            num++;
        }
        if (_constraints[cons_idx].is_equal) cout << " = ";
        else if (_constraints[cons_idx].is_less) cout << " <= ";
        else cout << " >= ";
        cout << _constraints[cons_idx].bound;
        cout << endl;
    }

    void qp_solver::print_mono(monomial mono)
    {
        cout.precision(15);
        if (mono.is_linear) 
            std ::cout << mono.coeff <<" * "<< _vars[mono.m_vars[0]].name;
        else
        {
            if (mono.is_multilinear)  std:: cout << mono.coeff << " * " << _vars[mono.m_vars[0]].name << " * " << _vars[mono.m_vars[1]].name;
            else  std:: cout << mono.coeff <<" * "<< _vars[mono.m_vars[0]].name << " ^ 2 "; 
        }
    }

    void qp_solver::print_imp_info()
    {
        //var information print
        cout << " var information print begin "<< endl;
        for (auto v : _vars)
        {
            cout << " var.index: " << v.index << " var.name: " << v.name;
            if (v.has_lower) cout << " has lower: " << v.lower;
            if (v.has_upper) cout << " has upper: " << v.upper;
            if (v.is_bin) cout <<" is bin ";
            if (v.is_int) cout <<" is int ";
            if (v.is_in_obj) cout <<" is in obj ";
            if (v.is_constant) cout <<" is is_constant ";
            if (v.equal_bound) cout <<" is equal_bound ";
            cout << endl << v.name << " have constraints : " << v.constraints.size() <<endl;
            int cons_num = 1;
            for (auto cons : v.constraints)
            {
                cout << cons_num << ": ";
                print_cons(cons);
                cons_num++;
            }
        }
        cout << endl << " bool vars size : " << _bool_vars.size() << " ";
        for (auto idx : _bool_vars)
        {
            cout << _vars[idx].name <<" ";
        }
        cout << endl << " int vars size : " << _int_vars.size() << " ";
        for (auto idx : _int_vars)
        {
            cout << _vars[idx].name <<" ";
        }
        cout << endl << " var information print finished "<< endl;


        //obj var_coeff print
        cout << endl << " var_obj_coeff begin "<< endl; 
        for (auto var_idx : _vars_in_obj)
        {
            var * v = &(_vars[var_idx]);
            cout <<" var name: "<< v->name << endl;
            cout << " var_obj_coeff: ";
            if (v->obj_quadratic_coeff != 0)
            {
                cout <<" quar coeff: "<< v->obj_quadratic_coeff << v->name << " ^ 2 ";
            }
            for (int linear_pos = 0; linear_pos < v->obj_linear_coeff.size(); linear_pos++)
            {
                if (linear_pos == 0) cout << " linear coeff: ( ";
                if (linear_pos != 0) cout << " + ";
                cout<< v->obj_linear_constant_coeff[linear_pos] <<" * "<< _vars[v->obj_linear_coeff[linear_pos]].name;
                if (linear_pos == v->obj_linear_coeff.size() - 1) cout << " ) " << v->name;
            }
            if (v->obj_constant_coeff != 0)
            {
                cout <<" constant coeff: "<< v->obj_constant_coeff << " * " << v->name;
            }
            cout << endl;
            for (int mono_pos : _vars[var_idx].obj_monomials)
            {
                print_mono(_object_monoials[mono_pos]);
                cout <<endl;
            }
        }
        cout << " var_obj_coeff finished "<< endl; 


        //cons  var_coeff print; 
        cout << " constraint var_coeff begin "<< endl; 
        for (auto cons : _constraints)
        {
            cout <<" constraint index: "<< cons.index << endl;
            for (auto v_c : cons.var_coeff)
            {
                cout << " var_name: " << _vars[v_c.first].name << ":" << endl;
                cout << " var_coeff: ";
                all_coeff coeff = v_c.second;
                if (coeff.obj_quadratic_coeff != 0)
                {
                    cout <<" quar coeff: "<< coeff.obj_quadratic_coeff << _vars[v_c.first].name << " ^ 2 ";
                }
                for (int linear_pos = 0; linear_pos < coeff.obj_linear_coeff.size(); linear_pos++)
                {
                    if (linear_pos == 0) cout << " linear coeff: ( ";
                    if (linear_pos != 0) cout << " + ";
                    cout<< coeff.obj_linear_constant_coeff[linear_pos] <<" * "<< _vars[coeff.obj_linear_coeff[linear_pos]].name;
                    if (linear_pos == coeff.obj_linear_coeff.size() - 1) cout << " ) " << _vars[v_c.first].name;
                }
                if (coeff.obj_constant_coeff != 0)
                {
                    cout <<" constant coeff: "<< coeff.obj_constant_coeff << " * " << _vars[v_c.first].name;
                }
                cout << endl;
            }
            cout << endl << endl << endl;
        }
        cout << " constraint var_coeff finished "<< endl; 
    }

    void qp_solver::print_lp_formula(bool is_all_obj)
    {
        add_bool_bound();
        int num = 0;
        bool quad_flag = false;
        // if (is_minimize) cout << "Minimize: " <<endl;
        // else cout << "Maximize: " << endl;
        cout << "Minimize" <<endl;
        cout << "obj: ";
        if (!is_all_obj)
            print_bounded_obj();
        else 
        {
            for (auto mono : _object_monoials)
            {
                // cout << "obj: ";
                // if (num != 0) cout << " + " ;
                if (num == 0) print_lp_mono(mono, true, quad_flag, true);
                else print_lp_mono(mono, false, quad_flag, true);
                num++;
            }
            if (quad_flag)
            {
                cout << " ]/2";
                quad_flag = false;
            }
        }
        // if (_obj_constant != 0) cout << " " << _obj_constant;
        cout << endl << endl;
        //没有等式怎么办，需要先确定约束再确定目标函数
        cout << "Subject To" << endl;
        for (auto cons : _constraints)
        {
            if (!cons.is_equal) continue;
            num = 0;
            cout << cons.name <<": ";
            for (auto mono : cons.monomials)
            {
                // if (num != 0) cout << " + " ;
                // print_mono(mono);
                if (num == 0) print_lp_mono(mono, true, quad_flag, false);
                else print_lp_mono(mono, false, quad_flag, false);
                num++;
            }
            if (quad_flag)
            {
                cout << " ]";
                quad_flag = false;
            }
            if (cons.is_equal) cout << " = ";
            else if (cons.is_less) cout << " <= ";
            else cout << " >= ";
            cout << cons.bound;
            cout << endl;
        }
        std::ostringstream buffer;
        int out_num = 0 ;
        buffer << "\n";
        buffer << "Bounds\n";
        for (auto var_idx : print_vars) 
        {
            const auto& cur = _vars[var_idx];
            if (cur.is_bin) continue;
            if (cur.is_constant)
            {
                buffer << cur.name << " = " << cur.constant;
            }
            if (!cur.has_lower && !cur.has_upper) 
            {
                buffer << cur.name << " Free\n";
                out_num++;
                continue;
            }
            else if (cur.has_lower && cur.has_upper)
            {
                out_num++;
                if (cur.lower == 0)
                    buffer << cur.name << " <= " << cur.upper << "\n";
                else 
                {
                    buffer << cur.lower << " <= "<< cur.name << " <= " << cur.upper << "\n";
                }
                    //  285.466096 <= x5506 <= 20952.39319
            }
            else 
            {
                if (cur.has_lower && cur.lower != 0) 
                {
                    out_num++;
                    buffer << cur.name << " >= " << cur.lower << "\n";
                } 
                else if (!cur.has_lower)
                {
                    out_num++;
                    buffer << "-inf" << " <= "<< cur.name << " <= " << cur.upper << "\n";
                }
            }
        }
        if (out_num != 0) cout << buffer.str();
        // cout << endl;
        // cout << "Bounds" << endl;
        // for (auto var_idx : print_vars)
        // {
        //     var cur = _vars[var_idx];
        //     Float ub, lb;
        //     if (cur.is_bin) continue;
        //     if (!cur.has_lower && !cur.has_upper) 
        //     {
        //         cout << _vars[var_idx].name << " Free" ;
        //         continue;
        //     }
        //     if (cur.has_lower && cur.lower != 0)
        //     {
        //         cout << _vars[var_idx].name << " >= " << cur.lower;
        //     }
        //     else if (!cur.has_lower) cout << _vars[var_idx].name << " >= -inf " ;
        //     if (cur.has_upper) cout << _vars[var_idx].name << " <= " << cur.upper;
        // }
        cout << endl;
        cout << "Binary" << endl;
        for (auto var_idx : print_vars)
        {
            var cur = _vars[var_idx];
            if (cur.is_bin) cout << cur.name << " ";
        }
        cout << endl << endl;
        cout << "End" << endl;
        //输出约束有关的变量属性和bound值，话说bound这个其实还是可以再想想的，尤其是在约束里的bound应该怎么处理！！！就像smt那样处理一下？
    }

    bool qp_solver::print_lp_mono(monomial mono, bool is_first, bool & is_quad, bool is_obj)
    {
        cout.precision(15);
        Float coeff = fabs(mono.coeff);
        if (!is_quad && !mono.is_linear)
        {
            if (!is_first)
                cout << " + [ ";
            else cout << " [ ";
            if (mono.coeff < 0) cout << " - ";
            is_quad = true;
        }
        else 
        {
            if (mono.coeff > 0 && !is_first)
                cout << " + ";
            else if (mono.coeff < 0 && !is_first)
                cout << " - ";
            else if (mono.coeff < 0 && is_first)
                cout << "- ";
        }
        if (mono.is_linear)
        {
            std::cout << coeff <<" "<< _vars[mono.m_vars[0]].name;
            print_vars.insert(mono.m_vars[0]);
            return false;
        }
        else
        {
            if (mono.is_multilinear) 
            {
                if (is_obj) coeff *= 2;
                std:: cout << coeff << " " << _vars[mono.m_vars[0]].name << " * " << _vars[mono.m_vars[1]].name;
                print_vars.insert(mono.m_vars[0]);
                print_vars.insert(mono.m_vars[1]);
            }
            else 
            {
                if (is_obj) coeff *= 2;
                std:: cout << coeff <<" "<< _vars[mono.m_vars[0]].name << "^2"; 
                print_vars.insert(mono.m_vars[0]);
            }
            return true;
        }
    }

    int qp_solver::read_init_solution(char * filename)
    {
        // return 0;
        //check一下无界的时候输出是什么
        freopen(filename,"r",stdin);
        // std::ifstream file2;
        // file2.open(filename, std::ifstream::in);
        // if (!file2.is_open()) {
        //     std::cerr << "Error: Could not open file " << filename << std::endl;
        //     return 1;
        // }
        // cout << filename<<endl;
        string line;
        int mode = -2;
        // cout <<"here 1" <<endl;
        while (getline(cin, line)) 
        {
            // cout << line << endl;
            if (line.find("solution status: optimal solution found") != std::string::npos)
            {
                mode = 1;
                continue;
            }
            else if (line.find("solution status: time limit reached") != std::string::npos)
            {
                mode = -1;
                continue;
            }
            else if (line.find("solution status: unbounded") != std::string::npos)
            {
                mode = 2;
                return mode;
            }
            else if (line.find("solution status: infeasible or unbounded") != std::string::npos)
            {
                mode = 2;
                // continue;
                return mode;
            }
            else if (line.find("solution status: unknown") != std::string::npos)
            {
                mode = 2;
                // continue;
                continue;
            }
            else if (line.find("solution status: infeasible") != std::string::npos)
            {
                mode = 2;
                // continue;
                continue;
            }
            else if (line.find("no solution available") != std::string::npos) return 0;
            if (line.find("objective value:") != std::string::npos) continue;
            else if (line.find("quadobjvar") != std::string::npos) continue;
            vector<string> read_vec;
            split_string(line, read_vec);
            // split_string(line, read_vec);
            // string line1 = "b2 1 (obj:53.15338392)";
            // std::istringstream stream(line);
            // string word;
            // while (stream >> word) 
            // {  // 默认按空格分隔
            //     read_vec.push_back(word);
            // }
            // cout << read_vec.size() << endl;
            // cout << read_vec[0] << endl;
            // cout << read_vec[1] << endl;
            string var_name = read_vec[0];
            int size;
            if (_vars_map.count(var_name) == 0) cout << " no variable in input but in solution file";
            else size = _vars_map[var_name];
            _init_solution_map[size] = stold(read_vec[1]);
            // cout << _init_solution_map[size] << " " << read_vec[1] << endl;
        }
        // file2.close();
        // cout <<"here 2" <<endl;
        // exit(0);
        fclose(stdin);
        return mode;
    }

    void qp_solver::print_bounded_obj()
    {
        int num = 0;
        bool quad_flag = false;
        // for (auto mono : _object_monoials)
        // {
        //     select_bounded_mono(mono);
        // }
        select_bounded_mono();
        for (auto mono : print_bounded_objs)
        {
            // cout << "obj: ";
            // if (num != 0) cout << " + " ;
            if (num == 0) print_lp_mono(mono, true, quad_flag, true);
            else print_lp_mono(mono, false, quad_flag, true);
            num++;
        }
        if (quad_flag)
        {
            cout << " ]/2";
            quad_flag = false;
        }
    }

    void qp_solver::select_bounded_mono()
    {
        var * obj_var; 
        unordered_set <int> selected_vars;
        for (auto var_idx : print_vars) 
        {
            obj_var = & (_vars[var_idx]);
            if (obj_var->is_bin) selected_vars.insert(var_idx);
            else if (obj_var->obj_quadratic_coeff != 0)
            {
                if (obj_var->obj_quadratic_coeff > 0) selected_vars.insert(var_idx);
                else if (obj_var->has_lower && obj_var->has_upper) selected_vars.insert(var_idx);
            }
            else if (obj_var->obj_linear_coeff.size() != 0)
            {
                //do nothing?
            }
            else if (obj_var->obj_constant_coeff != 0) 
            {
                if (obj_var->obj_constant_coeff > 0 && obj_var->has_lower) selected_vars.insert(var_idx);
                else if (obj_var->obj_constant_coeff < 0 && obj_var->has_upper) selected_vars.insert(var_idx);
            }
        }
        for (auto mono : _object_monoials)
        {
            if (mono.coeff == 0) 
            {
                cout << "mono.coeff == 0 ???";
                return;
            }
            if (!mono.is_multilinear)
            {
                int idx = mono.m_vars[0];
                if (selected_vars.count(idx) != 0)
                    print_bounded_objs.push_back(mono);
            }
            else if (mono.is_multilinear)
            {
                var cur_1= _vars[mono.m_vars[0]];
                var cur_2= _vars[mono.m_vars[1]];
                if (cur_1.is_bin && cur_2.is_bin) print_bounded_objs.push_back(mono);
                else if (mono.coeff > 0)
                {
                    if (cur_1.is_bin && cur_2.has_lower) print_bounded_objs.push_back(mono);
                    else if (cur_2.is_bin && cur_2.has_lower) print_bounded_objs.push_back(mono);
                    else if (cur_1.has_lower && cur_2.has_lower)
                    {
                        if (cur_1.lower >= 0 && cur_2.lower >= 0) print_bounded_objs.push_back(mono);
                        //thinking
                        //TODO: 1.想这里的逻辑 2.想怎么先后顺序搞一下cons和obj 3.把函数顺序全部调整好 4.想想还有没有更好的做法
                        //check 逻辑，写b作为bound的逻辑
                    }
                }
                else if (mono.coeff < 0)
                {
                    if (cur_1.is_bin && cur_2.has_upper) print_bounded_objs.push_back(mono);
                    else if (cur_2.is_bin && cur_2.has_upper) print_bounded_objs.push_back(mono);
                    else if (cur_1.has_lower && cur_2.has_lower && cur_1.has_upper && cur_2.has_upper)
                    {
                        if (cur_1.lower >= 0 && cur_2.lower >= 0) print_bounded_objs.push_back(mono);
                        //thinking
                    }
                }
            }
        }
    }
        
    void qp_solver::add_bool_bound()
    {
        Float lb, ub;
        int real_num;
        int bool_num;
        int all_num;
        int real_idx;
        Float real_var_coeff;
        var * real_var;
        for (auto con : _constraints)
        {
            real_num = 0;
            bool_num = 0;
            all_num = 0;
            lb = 0; ub = 0;
            if (con.is_equal)
            {
                for (auto var_coeff : con.var_coeff)
                    print_vars.insert(var_coeff.first);
            }// 插入等式中的变量
            if (con.monomials.size() > 2 || con.bound != 0) continue;
            for (auto mono : con.monomials)
            {
                if (!mono.is_linear) 
                {
                    real_num = 10;
                    break;
                }
                all_num++;
                var cur = _vars[mono.m_vars[0]];
                if (cur.is_bin) 
                {
                    bool_num++;
                    ub = mono.coeff;
                    lb = mono.coeff;
                    // if (mono.coeff > 0)
                    //     ub += mono.coeff;
                    // else 
                    //     lb += mono.coeff;
                }
                else 
                {
                    real_num++;
                    real_var_coeff = mono.coeff;
                    real_idx = mono.m_vars[0];
                }
                if (real_num == 2) break;
            }
            if (real_num != 1) continue;
            if (all_num != bool_num + 1) continue;
            real_var = &(_vars[real_idx]);
            lb /= (-real_var_coeff);
            ub /= (-real_var_coeff);
            lb += con.bound / real_var_coeff;
            ub += con.bound / real_var_coeff;
            if (lb < 0) ub = fabs(ub);
            else lb = -fabs(lb);
            // if (real_var_coeff > 0) std::swap(lb,ub);
            if (con.is_equal)
            {
                if (lb > real_var->lower || !real_var->has_lower)
                    real_var->lower = lb;
                if (ub < real_var->upper || !real_var->has_upper)
                    real_var->upper = ub;
                if (!real_var->has_lower) real_var->has_lower = true;
                if (!real_var->has_upper) real_var->has_upper = true;
            }
            else if (con.is_less)
            {
                if (real_var_coeff > 0)
                {
                    if (ub < real_var->upper || !real_var->has_upper)
                        real_var->upper = ub;
                    if (!real_var->has_upper) real_var->has_upper = true;
                }
                else 
                {
                    if (lb > real_var->lower || !real_var->has_lower)
                        real_var->lower = lb;
                    if (!real_var->has_lower) real_var->has_lower = true;
                }
            }
            else 
            {
                if (real_var_coeff > 0)
                {
                    if (lb > real_var->lower || !real_var->has_lower)
                        real_var->lower = lb;
                    if (!real_var->has_lower) real_var->has_lower = true;
                }
                else 
                {
                    if (ub < real_var->upper || !real_var->has_upper)
                        real_var->upper = ub;
                    if (!real_var->has_upper) real_var->has_upper = true;
                }
            }
        }
    }

}