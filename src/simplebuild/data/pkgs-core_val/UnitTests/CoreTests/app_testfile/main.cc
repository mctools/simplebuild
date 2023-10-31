#include "Core/File.hh"
#include <sys/stat.h>//for chmod
#include <cstdlib>
#include <unistd.h> // getuid

int testfail(const char * msg) {
  printf("Test failed : %s\n",msg);
  return 1;
}

int main(int,char**) {

  //Test permissions, disabling some test when running via sudo or as root
  //(happens in bitbucket pipelines for instance).

  const bool is_superuser(!getuid()||!geteuid());

  //First an executable file to which we should not have write access:
  if (!Core::file_exists("/bin/ls")) return testfail("/bin/ls exists");
  if (!Core::file_exists_and_readable("/bin/ls")) return testfail("/bin/ls r");
  if (Core::file_exists_and_writable("/bin/ls")&&!is_superuser) return testfail("/bin/ls w");
  if (!Core::file_exists_and_executable("/bin/ls")) return testfail("/bin/ls x");
  if (Core::isdir("/bin/ls")) return testfail("/bin/ls isdir");

  //Same with a directory:
  if (!Core::file_exists("/bin")) return testfail("/bin exists");
  if (!Core::file_exists_and_readable("/bin")) return testfail("/bin r");
  if (Core::file_exists_and_writable("/bin")&&!is_superuser) return testfail("/bin w");
  if (!Core::file_exists_and_executable("/bin")) return testfail("/bin x");
  if (!Core::isdir("/bin")) return testfail("/bin isdir");

  //Next a file which we should really have no access to: (TODO: Similar test on OSX?)
  if (Core::file_exists("/etc/shadow")) {
    if (Core::file_exists_and_readable("/etc/shadow")&&!is_superuser) return testfail("/etc/shadow r");
    if (Core::file_exists_and_writable("/etc/shadow")&&!is_superuser) return testfail("/etc/shadow w");
    if (Core::file_exists_and_executable("/etc/shadow")) return testfail("/etc/shadow x");
    if (Core::isdir("/etc/shadow")) return testfail("/etc/shadow isdir");
  }

  //Same with a dir: (TODO: Similar test on OSX?)
  if (Core::file_exists("/root")) {
    if (Core::file_exists_and_readable("/root")&&!is_superuser) return testfail("/root r");
    if (Core::file_exists_and_writable("/root")&&!is_superuser) return testfail("/root w");
    if (Core::file_exists_and_executable("/root")&&!is_superuser) return testfail("/root x");
    if (!Core::isdir("/root")) return testfail("/root isdir");
  }

  //Some non-existing file/dir:
  if (Core::file_exists("dummyne")) return testfail("dummyne exists");
  if (Core::isdir("dummyne")) return testfail("dummyne isdir");
  if (Core::file_exists_and_readable("dummyne")) return testfail("dummyne r");
  if (Core::file_exists_and_writable("dummyne")) return testfail("dummyne w");
  if (Core::file_exists_and_executable("dummyne")) return testfail("dummyne x");

  //create dummy:
  FILE * out = fopen("dummy", "w");
  if (!out)
    return testfail("failed to create dummy");
  fprintf(out,"#!/usr/bin/env bash\necho Test output of executable script\n");
  fclose(out);

  if (!Core::file_exists("dummy")) return testfail("dummy exists");
  if (Core::isdir("dummy")) return testfail("dummy isdir");

  if (mkdir("dummydir",0))
    return testfail("failed to create dummydir");

  if (!Core::file_exists("dummydir")) return testfail("dummydir exists");
  if (!Core::isdir("dummydir")) return testfail("dummydir isdir");

  for (int isdir = 0; isdir < 2; ++isdir) {
    const char * filename = isdir ? "dummydir" : "dummy";
    for (int r = 0; r < 2; ++r)
      for (int w = 0; w < 2; ++w)
        for (int x = 0; x < 2; ++x) {
          printf("Testing file with drwx = %i%i%i%i\n",isdir,r,w,x);
          if (chmod(filename,0400*r+0200*w+0100*x)) return testfail("test file: chmod");
          if (!Core::file_exists(filename)) return testfail("test file: exists");
          if ( isdir != Core::isdir(filename) ) return testfail("test file: isdir");
          if ( isdir ) {
            printf("  => skipping r/w/x test on dir (since chmod does not change directory perms on AFS)\n");
            continue;
          }
          if ( r != (int) Core::file_exists_and_readable(filename) && !is_superuser ) return testfail("test file: r");
          if ( w != (int) Core::file_exists_and_writable(filename) && !is_superuser ) return testfail("test file: w");
          if ( x != (int) Core::file_exists_and_executable(filename) ) return testfail("test file: x");
        }
  }

  int ec = system("./dummy");
  return ec == 0 ? 0 : testfail("run ./dummy");
}
