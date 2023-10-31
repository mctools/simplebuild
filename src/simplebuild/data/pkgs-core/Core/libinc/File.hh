#ifndef Core_File_hh
#define Core_File_hh

#include <string>

namespace Core {

  bool file_exists(const char * filepath);
  bool file_exists_and_readable(const char * filepath);
  bool file_exists_and_writable(const char * filepath);
  bool file_exists_and_executable(const char * filepath);
  bool isdir(const char * filepath);

  //convenience overloads for std::string:
  inline bool file_exists(const std::string& filepath)
  {
    return file_exists(filepath.c_str());
  }

  inline bool file_exists_and_readable(const std::string& filepath)
  {
    return file_exists_and_readable(filepath.c_str());
  }

  inline bool file_exists_and_writable(const std::string& filepath)
  {
    return file_exists_and_writable(filepath.c_str());
  }

  inline bool file_exists_and_executable(const std::string& filepath)
  {
    return file_exists_and_executable(filepath.c_str());
  }

  inline bool isdir(const std::string& filepath)
  {
    return isdir(filepath.c_str());
  }

}

#endif
