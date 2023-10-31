#include "Core/FindData.hh"
#include "Core/String.hh"
#include "Core/File.hh"
#include <cstring>
#include <cstdlib>

std::string Core::findData(const char* pkg,const char* filename)
{
  std::string s=getenv("SBLD_DATA_DIR");
  s+="/";
  s+=pkg;
  s+="/";
  s+=filename;

  if (!Core::file_exists(s))
    return "";

  return s;
}


std::string Core::findData(const char* filename)
{
  std::vector<std::string> parts;
  Core::split(parts,filename,"/");
  if (parts.size()==2&&!parts[0].empty()&&parts[0][0]!='/') {
    std::string res = findData(parts[0].c_str(),parts[1].c_str());
    if (res.empty()&&Core::file_exists(filename))
      return filename;
    return res;
  }

  if (!Core::file_exists(filename))
    return "";

  return filename;
}

char* core_finddata(const char*pkg,const char*filename)
{
  static char fn[512];
  std::string f = Core::findData(pkg,filename);
  if (f.empty())
    return 0;
  std::strncpy(fn,f.c_str(),sizeof(fn));
  fn[sizeof(fn)-1]='\0';
  return fn;
}
