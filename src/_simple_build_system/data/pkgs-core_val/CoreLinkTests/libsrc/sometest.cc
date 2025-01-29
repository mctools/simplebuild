#include "NCrystal/NCrystal.hh"

#if NCRYSTAL_VERSION >= 3009080
#  include "NCrystal/internal/utils/NCString.hh"
#else
#  include "NCrystal/internal/NCString.hh"
#endif

int sbld_ncrystaltests_impl()
{
  auto info = NCrystal::createInfo("stdlib::Al_sg225.ncmat"
                                   ";vdoslux=0;dcutoff=0.5");
  NCrystal::dump( info );

  std::string tmp = "  hejsa \t\n";
  tmp = NCrystal::trim2(tmp);
  if ( tmp.size()!=5 )
    return 1;

  return 0;
}
