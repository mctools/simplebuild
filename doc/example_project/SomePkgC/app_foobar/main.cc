#include <iostream>
#include "zlib.h"

int main()
{
  std::cout << "I am a silly little C++ application" << std::endl;
  std::cout << "I am built against zlib in version: "
            << ZLIB_VERSION << std::endl;
}
