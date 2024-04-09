#include <iostream>

//A bit misleading command name, for backwards compat.
int main()
{
#ifndef NDEBUG
  std::cout<<"DEBUG"<<std::endl;
#else
  std::cout<<"RELEASE"<<std::endl;
#endif
  return 0;
}
