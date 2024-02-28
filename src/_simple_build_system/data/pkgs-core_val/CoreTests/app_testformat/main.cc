#include "Core/Types.hh"
#include <cstdio>
#include <sstream>//for 32bit SLC6 workaround

int main(int,char**) {
  printf("Test unsigned:  %20u\n",unsigned(4000000000u));
  printf("Test      int:  %20i\n",int(-2000000000));
  printf("Test  uint8_t:  %20" PRIu8 "\n",std::uint8_t(250));//space around PRIu8 needed for gcc 4.7
  printf("Test   int8_t:  %20" PRIi8 "\n",int8_t(-100));
  printf("Test uint16_t:  %20" PRIu16 "\n",std::uint16_t(60000));
  printf("Test  int16_t:  %20" PRIi16 "\n",int16_t(-10000));
  printf("Test uint32_t:  %20" PRIu32 "\n",std::uint32_t(4000000000u));
  printf("Test  int32_t:  %20" PRIi32 "\n",int32_t(-2000000000));
  //This should work, but does not with gcc 4.4 on 32 bit SLC6:
  //printf("Test uint64_t:  %20" PRIu64 "\n",UINT64_C(18000000000000000000));
  //printf("Test  int64_t:  %20" PRIi64 "\n",INT64_C(-9000000000000000000));
  std::ostringstream s1;s1<<UINT64_C(18000000000000000000);
  std::ostringstream s2;s2<< INT64_C(-9000000000000000000);
  printf("Test uint64_t:  %20s\n",s1.str().c_str());
  printf("Test  int64_t:  %20s\n",s2.str().c_str());

  return 0;
}
