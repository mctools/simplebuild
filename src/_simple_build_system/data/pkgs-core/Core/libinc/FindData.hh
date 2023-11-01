#ifndef Core_FindData_hh
#define Core_FindData_hh

#ifdef __cplusplus

#include <string>

namespace Core {

  std::string findData(const char* pkg,const char* filename);

  //Second form which can be used to decode either absolute paths or paths of the form "<pkg>/<file>":
  std::string findData(const char* filename);

  //Convenience wrappers to accept std::strings directly:
  inline std::string findData(const std::string& filename) { return findData(filename.c_str()); }
  inline std::string findData(const std::string& pkg,const std::string& filename)  { return findData(pkg.c_str(),filename.c_str()); }
  inline std::string findData(const std::string& pkg,const char* filename)  { return findData(pkg.c_str(),filename); }
  inline std::string findData(const char* pkg,const std::string& filename)  { return findData(pkg,filename.c_str()); }

}

extern "C" {
#endif
//For C programs (returned string will be valid until core_finddata is next called):
char* core_finddata(const char* pkg, const char* filename);
#ifdef __cplusplus
}
#endif
#endif
