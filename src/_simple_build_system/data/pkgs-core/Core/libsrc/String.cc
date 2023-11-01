#include "Core/String.hh"
#include <stdexcept>
#include <cstring>

bool Core::ends_with(const std::string& str, const std::string& ending)
{
  auto nstr = str.size();
  auto nend = ending.size();
  if (nend>nstr)
    return false;
  const char * cstr = &str[nstr-nend];
  const char * cstrE = cstr + nend;
  const char * cending = &ending[0];
  while (cstr!=cstrE) {
    if (*cstr++ != *cending++)
      return false;
  }
  return true;
}

bool Core::starts_with(const std::string& str, const std::string& start)
{
  auto nstr = str.size();
  auto nstart = start.size();
  if (nstart>nstr)
    return false;
  const char * cstr = &str[0];
  const char * cstrE = cstr + nstart;
  const char * cstart = &start[0];
  while (cstr!=cstrE) {
    if (*cstr++ != *cstart++)
      return false;
  }
  return true;
}

void Core::split_noempty( std::vector<std::string>& parts,
                          const std::string& str,
                          const std::string& delims )
{
  if (delims.empty())
    throw std::runtime_error("empty delimiter string");
  //Split str on whitespace (" \t\n") with minimal memory allocations and
  //copying, discarding whitespace which is either leading and trailing or
  //repeating.
  const char * c = &str[0];
  const char * cE = c + str.size();
  const char * partbegin = 0;
  while (true) {
    if (c==cE||std::strchr(delims.c_str(),*c)) {
      if (partbegin) {
        parts.push_back(std::string(partbegin,c-partbegin));
        partbegin=0;
      }
      if (c==cE)
        return;
    } else if (!partbegin) {
      partbegin = c;
    }
    ++c;
  }
}

void Core::split( std::vector<std::string>& parts,
                  const std::string& str,
                  const std::string& delims )
{
  if (delims.empty())
    throw std::runtime_error("empty delimiter string");
  //Split str on whitespace (" \t\n") with minimal memory allocations and
  //copying, discarding whitespace which is either leading and trailing or
  //repeating.
  const char * c = &str[0];
  const char * cE = c + str.size();
  const char * partbegin = c;
  while (true) {
    if (c==cE||std::strchr(delims.c_str(),*c)) {
      parts.push_back(std::string(partbegin,c-partbegin));//Todo: emplace_back
      if (c==cE)
        return;
      partbegin = ++c;
    } else {
      ++c;
    }
  }
}

void Core::to_lower(std::string& s)
{
  char * c = &(s[0]);
  char * cE = c + s.size();
  for (;c!=cE;++c) {
    if (*c>='A' && *c<='Z')
      *c = *c + ('a'-'A');
  }
}

bool Core::contains_only(const std::string & str, const std::string & list)
{
  return str.find_first_not_of(list) == std::string::npos;
}

void Core::replace(std::string& str, const std::string& from, const std::string& to) {
  //from https://stackoverflow.com/questions/3418231/replace-part-of-a-string-with-another-string
  if (from.empty())
    return;
  std::size_t start_pos = 0;
  while((start_pos = str.find(from, start_pos)) != std::string::npos) {
    str.replace(start_pos, from.length(), to);
    start_pos += to.length();
  }
}
