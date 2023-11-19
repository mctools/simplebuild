#include "Core/Types.hh"
#include <cmath>
#include <string>
#include <iostream>

int main( int argc, char** )
{
  //Usage of std::signbit might fail on osx in case of wrong -isysroot:
  double x = (double)(argc);
  std::cout<<"signbit test "<<bool(std::signbit(x))<<std::endl;
  return 0;
}
