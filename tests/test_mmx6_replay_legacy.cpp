/* A missing SDK service must never turn an explicit replay into live input. */
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_diagnostics.cpp"
#include <cassert>
static unsigned registrations;
extern "C" int psx_mod_register_activation_plugin(const char*,void (*)(void)){++registrations;return 1;}
int main(int argc,char**){
    if(argc>1){
#ifdef _WIN32
        assert(_putenv_s("MMX6_INPUT_REPLAY","explicit-request")==0);
#else
        assert(setenv("MMX6_INPUT_REPLAY","explicit-request",1)==0);
#endif
    }
    mmx6_register_diagnostics_unavailable();
    assert(argc==1&&registrations==1);
}
