#include "Core/String.hh"

void test_split(const char * s,const char * delim) {
  std::vector<std::string> parts;
  Core::split(parts,s,delim);
  printf("Core::split         \"%s\" on \"%s\" yields %i parts:",s,delim,(int)parts.size());
  for (auto it = parts.begin(); it!=parts.end(); ++it)
    printf(" \"%s\"",it->c_str());
  printf("\n");
  parts.clear();
  Core::split_noempty(parts,s,delim);
  printf("Core::split_noempty \"%s\" on \"%s\" yields %i parts:",s,delim,(int)parts.size());
  for (auto it = parts.begin(); it!=parts.end(); ++it)
    printf(" \"%s\"",it->c_str());
  printf("\n");
}

void test_endswith(const char * s,const char * e) {
  printf("endswith(\"%s\",\"%s\") = %i\n",s,e,Core::ends_with(s,e));
}
void test_startswith(const char * s,const char * e) {
  printf("startswith(\"%s\",\"%s\") = %i\n",s,e,Core::starts_with(s,e));
}

int main(int,char**) {

  test_split("lala;bla",";");
  test_split("lala;/bla",";/");
  test_split("lala bla"," ");
  test_split(""," ");
  test_split("lala;bla;",";");
  test_split(";;",";");

  test_endswith("b",".txt");
  test_endswith("",".txt");
  test_endswith(".txt",".txt");
  test_endswith("bla.txt",".txt");
  test_endswith("bla.txt.png",".txt");
  test_endswith(".txt.bla.txt",".txt");
  test_endswith(".txtbla",".txt");
  test_endswith(".png.txt.bla",".txt");

  test_startswith("b",".txt");
  test_startswith("",".txt");
  test_startswith(".txt",".txt");
  test_startswith("bla.txt",".txt");
  test_startswith("bla.txt.png",".txt");
  test_startswith(".txt.bla.txt",".txt");
  test_startswith(".txtbla",".txt");
  test_startswith(".png.txt.bla",".txt");

  return 0;
}
