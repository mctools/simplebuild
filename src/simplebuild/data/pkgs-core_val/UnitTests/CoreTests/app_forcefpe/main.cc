#include "Core/FPE.hh"
#include "Core/Types.hh"
#include <cstdio>
#include <cmath>
#include <stdexcept>

//NB: DBL_MAX*2.0 => floating point overflow

//static int fpetest_zeroint = 0;
//static double fpetest_zerodbl = 0;

double somebadfunc()
{
  //return double(123/fpetest_zeroint);//FPE_INTDIV
  //return DBL_MAX*2;//FPE_FLTOVF
  //return DBL_MIN*0.1;//FPE_FLTUND
  //return 1.0/fpetest_zerodbl;//FPE_FLTDIV
  return sqrt(-1.0);//FPE_FLTINV
}

double somefuncB()
{
  return somebadfunc();
}

double somefuncA()
{
  return somefuncB();
}

int main(int,char**)
{

  Core::catch_fpe();

  try {
    printf("Some calculation gives: %f\n",somefuncA());
  } catch ( const Core::FloatingPointException& e ) {
    return 134;
  }


  return 0;
}
