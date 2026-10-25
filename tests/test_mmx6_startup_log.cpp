#include "mmx6_startup_log.h"
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <thread>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <io.h>
#define FD_CLOSE _close
#define FD_WRITE _write
#else
#include <unistd.h>
#define FD_CLOSE close
#define FD_WRITE write
#endif
#define CHECK(value) do {if(!(value)) {std::printf("line%d: %s\n",__LINE__,#value);return 1;}} while(0)

static std::string read_file(const std::filesystem::path& path) {
    std::ifstream input(path,std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(input)),{});
}
static bool contains_live(const std::filesystem::path& path,const std::string& expected) {
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    do {
        if(read_file(path).find(expected)!=std::string::npos)return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }while(std::chrono::steady_clock::now()<deadline);
    return false;
}

#ifdef _WIN32
static int launch_without_handles(const std::filesystem::path& root,const std::string& mode) {
    wchar_t executable[32768];
    CHECK(GetModuleFileNameW(nullptr,executable,32768));
    auto command=L"\""+std::wstring(executable)+L"\" \""+root.wstring()+L"\" child-"+
                 std::wstring(mode.begin(),mode.end());
    STARTUPINFOW startup{};startup.cb=sizeof startup;
    startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_HIDE;
    HANDLE console_output=INVALID_HANDLE_VALUE;
    if(mode=="tee") {
        std::filesystem::create_directories(root);
        SECURITY_ATTRIBUTES inheritable{sizeof inheritable,nullptr,TRUE};
        console_output=CreateFileW((root/"console.txt").c_str(),GENERIC_WRITE,FILE_SHARE_READ,
                                   &inheritable,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        CHECK(console_output!=INVALID_HANDLE_VALUE);
    }
    if(mode!="detached") {
        startup.dwFlags|=STARTF_USESTDHANDLES;
        auto handle=mode=="invalid"?INVALID_HANDLE_VALUE:nullptr;
        startup.hStdInput=startup.hStdOutput=startup.hStdError=handle;
        if(mode=="tee")startup.hStdError=console_output;
    }
    PROCESS_INFORMATION process{};
    bool created=CreateProcessW(executable,command.data(),nullptr,nullptr,mode=="tee",DETACHED_PROCESS,
                                nullptr,nullptr,&startup,&process)!=FALSE;
    if(console_output!=INVALID_HANDLE_VALUE)CloseHandle(console_output);
    CHECK(created);
    DWORD waited=WaitForSingleObject(process.hProcess,10000),code=1;
    if(waited!=WAIT_OBJECT_0)TerminateProcess(process.hProcess,1);
    bool obtained=GetExitCodeProcess(process.hProcess,&code)!=FALSE;
    CloseHandle(process.hThread);CloseHandle(process.hProcess);
    CHECK(waited==WAIT_OBJECT_0);
    CHECK(obtained && code==0);
    if(mode=="tee") {
        auto console=read_file(root/"console.txt");
        CHECK(console.find("mmx6.startup:")!=std::string::npos);
        CHECK(console.find("startup failure fixture")!=std::string::npos);
        for(unsigned i=0;i<5;++i)CHECK(console.find(std::string(4096,(char)('a'+i)))!=std::string::npos);
        CHECK(console.find("raw stderr fixture")!=std::string::npos);
        CHECK(console.find("native stderr fixture")!=std::string::npos);
    }else CHECK(read_file(root/"launch-state.txt").find("fileno=-2")!=std::string::npos);
    return 0;
}
#endif

int main(int argc,char **argv) {
    CHECK(argc>=2);
    auto root=std::filesystem::u8path(argv[1]);
    std::string mode=argc>2?argv[2]:"";
    bool detached_pointer_failure=false;
#ifdef _WIN32
    if(mode=="detached" || mode=="null" || mode=="invalid" || mode=="tee" ||
       mode=="detached-pointer-unavailable")return launch_without_handles(root,mode);
    if(mode.rfind("child-",0)==0 && mode!="child-tee") {
        CHECK(GetConsoleWindow()==nullptr);
        // Windows can normalize invalid STARTUPINFO handles to NULL. Keep a
        // genuinely invalid Win32 error handle for the explicit invalid case.
        if(mode=="child-invalid")CHECK(SetStdHandle(STD_ERROR_HANDLE,INVALID_HANDLE_VALUE));
        auto handle=GetStdHandle(STD_ERROR_HANDLE);
        CHECK(handle==nullptr || handle==INVALID_HANDLE_VALUE);
        if(mode=="child-invalid")CHECK(handle==INVALID_HANDLE_VALUE);
        std::filesystem::create_directories(root);
        std::ofstream state(root/"launch-state.txt");
        state<<"fileno="<<_fileno(stderr)<<" standard_handle="<<(intptr_t)handle<<'\n';
        state.close();
        CHECK(_fileno(stderr)==-2);
        if(mode=="child-detached-pointer-unavailable") {
            detached_pointer_failure=true;mode="pointer-unavailable";
        }
    }
#endif
    if(mode=="unavailable") {
        std::filesystem::create_directories(root);
        std::ofstream obstruction(root/"saves",std::ios::trunc);obstruction<<"fixture";obstruction.close();
        std::ofstream stale(root/"startup-log-location.txt",std::ios::trunc);stale<<"old.log\n";stale.close();
        CHECK(!mmx6_startup_log_begin(argv[1]));
        CHECK(std::string(mmx6_startup_log_path()).empty());
        CHECK(read_file(root/"startup-log-location.txt").find("logging unavailable:")!=std::string::npos);
        CHECK(!mmx6_startup_log_begin(argv[1]));
        return 0;
    }
    if(mode=="pointer-unavailable") {
        std::filesystem::create_directories(root/"startup-log-location.txt");
        CHECK(!mmx6_startup_log_begin(argv[1]));
        CHECK(std::string(mmx6_startup_log_path()).empty());
        if(detached_pointer_failure) {
            std::filesystem::path latest;
            for(const auto& entry:std::filesystem::directory_iterator(root/"saves"/"diagnostics"))
                if(entry.is_regular_file() && entry.path().extension()==".log" &&
                   entry.path().filename()>latest.filename())latest=entry.path();
            CHECK(!latest.empty());
            CHECK(contains_live(latest,"logging unavailable: cannot write startup log location"));
        }
        CHECK(!mmx6_startup_log_begin(argv[1]));
        return 0;
    }
    if(mode=="closed") {std::fflush(stderr);FD_CLOSE(2);}
    CHECK(mmx6_startup_log_begin(argv[1]));
    std::string path=mmx6_startup_log_path();
    CHECK(mmx6_startup_log_begin(argv[1]));
    CHECK(path==mmx6_startup_log_path());
    CHECK(contains_live(std::filesystem::u8path(path),"mmx6.startup:"));
    std::string expected="startup failure fixture\n";
    for(unsigned i=0;i<5;++i)expected+=std::string(4096,(char)('a'+i))+"\n";
    CHECK(std::fwrite(expected.data(),1,expected.size(),stderr)==expected.size());
    CHECK(std::fflush(stderr)==0);
    CHECK(contains_live(std::filesystem::u8path(path),expected));
    std::string raw="raw stderr fixture\n";
    CHECK(FD_WRITE(2,raw.data(),(unsigned)raw.size())==(int)raw.size());
    CHECK(contains_live(std::filesystem::u8path(path),raw));
#ifdef _WIN32
    std::string native="native stderr fixture\n";DWORD written=0;
    CHECK(WriteFile(GetStdHandle(STD_ERROR_HANDLE),native.data(),(DWORD)native.size(),&written,nullptr));
    CHECK(written==native.size());
    CHECK(contains_live(std::filesystem::u8path(path),native));
#endif
    mmx6_startup_log_end();
    std::string contents=read_file(std::filesystem::u8path(path));
    CHECK(contents.find(expected)!=std::string::npos);
    CHECK(contents.find("mmx6.startup:")!=std::string::npos);
    std::ifstream pointer(root/"startup-log-location.txt");
    std::string pointed;std::getline(pointer,pointed);CHECK(pointed==path);
    return 0;
}
