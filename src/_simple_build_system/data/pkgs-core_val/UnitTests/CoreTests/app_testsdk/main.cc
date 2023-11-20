#include <cmath>

int main( int argc, char** )
{
  //Usage of std::signbit might fail on osx in case of wrong -isysroot:
  double x = (double)(argc);
  return std::signbit(x) ? 1 : 0 ;
}
