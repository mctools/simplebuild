#include "Core/File.hh"
#include <unistd.h>
#include <sys/stat.h>

bool Core::file_exists(const char * path)
{
  return access(path, F_OK) == 0;
}

bool Core::file_exists_and_readable(const char * path)
{
  return access(path, R_OK) == 0;
}

bool Core::file_exists_and_writable(const char * path)
{
  return access(path, W_OK) == 0;
}

bool Core::file_exists_and_executable(const char * path)
{
  return access(path, X_OK) == 0;
}

bool Core::isdir(const char * path)
{
  if (!file_exists(path))
    return false;
  struct stat sb;
  return stat(path, &sb) == 0 && S_ISDIR(sb.st_mode);
  // S_ISDIR — directory
  // S_ISREG — regular file
  // S_ISCHR — character device
  // S_ISBLK — block device
  // S_ISFIFO — FIFO
  // S_ISLNK — symbolic link
  // S_ISSOCK — socket
}
