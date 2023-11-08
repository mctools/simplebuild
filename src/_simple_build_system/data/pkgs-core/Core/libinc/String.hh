#ifndef Core_String_hh
#define Core_String_hh

#include <string>
#include <vector>

//A few basic string utilities

namespace Core {

  bool ends_with(const std::string& str, const std::string& ending);
  bool starts_with(const std::string& str, const std::string& start);

  //Split str at any char in delims and push_back the resulting fragments on parts
  void split(std::vector<std::string>& parts,
             const std::string& str,
             const std::string& delims = " \t\n");

  //Same, but ignore empty parts:
  void split_noempty(std::vector<std::string>& parts,
                     const std::string& str,
                     const std::string& delims = " \t\n");

  //lowercase
  void to_lower(std::string&);

  //Check if all characters in str is in list:
  bool contains_only(const std::string & str, const std::string & list);

  //replace all occurances of from with to in str:
  void replace(std::string& str, const std::string& from, const std::string& to);

}

//Convenience macros for stringification:
#ifdef sbld_xstringify
#  undef sbld_xstringify
#endif
#ifdef sbld_stringify
#  undef sbld_stringify
#endif
#define sbld_xstringify(s) #s
#define sbld_stringify(s) sbld_xstringify(s)

#endif
