CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17
LDLIBS ?= -lgsl -lgslcblas -lm
SRCS = call.cpp component.cpp ls_balance.cpp ls_bin.cpp ls_mix_not_dis.cpp ls_no_cons.cpp ls_read.cpp
OBJS = $(SRCS:%.cpp=build/%.o)
TARGET = build/LS-IQCQP
all: $(TARGET)
$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) $(OBJS) -o $@ $(LDLIBS)
build/%.o: %.cpp sol.h util.h
	mkdir -p build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@
.PHONY: all
