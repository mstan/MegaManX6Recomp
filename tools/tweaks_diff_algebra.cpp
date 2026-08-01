// Streaming byte/sector algebra check for MMX6 Tweaks reference images.
//
// Usage:
//   tweaks_diff_algebra B.bin T.bin S.bin TS.bin
//
// B is the common Tweaks base, T is title-only, S is script-only, and TS is
// their combined reference output. The tool verifies that the independent
// deltas from B compose exactly into TS and reports collisions.

#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <vector>

namespace {

constexpr std::uint64_t kRawSectorSize = 2352;
constexpr std::size_t kBufferSize = 4 * 1024 * 1024;

struct Run {
    std::uint64_t begin;
    std::uint64_t end;
};

struct Metric {
    std::uint64_t bytes = 0;
    std::uint64_t run_count = 0;
    bool active = false;
    std::uint64_t run_begin = 0;
    std::uint64_t previous = 0;
    std::set<std::uint64_t> sectors;
    std::vector<Run> first_runs;

    void mark(std::uint64_t offset) {
        ++bytes;
        sectors.insert(offset / kRawSectorSize);
        if (!active) {
            active = true;
            run_begin = previous = offset;
        } else if (offset == previous + 1) {
            previous = offset;
        } else {
            finish_run();
            active = true;
            run_begin = previous = offset;
        }
    }

    void finish() {
        if (active) {
            finish_run();
        }
    }

private:
    void finish_run() {
        ++run_count;
        if (first_runs.size() < 100) {
            first_runs.push_back({run_begin, previous + 1});
        }
        active = false;
    }
};

struct Input {
    std::ifstream stream;
    std::uint64_t size = 0;
    std::vector<unsigned char> buffer;

    explicit Input(const char* path)
        : stream(path, std::ios::binary), buffer(kBufferSize) {
        if (!stream) {
            throw std::runtime_error(std::string("cannot open ") + path);
        }
        stream.seekg(0, std::ios::end);
        size = static_cast<std::uint64_t>(stream.tellg());
        stream.seekg(0);
    }

    void read(std::uint64_t offset, std::size_t count) {
        std::fill(buffer.begin(), buffer.begin() + count, 0);
        if (offset >= size) {
            return;
        }
        const auto available = static_cast<std::size_t>(
            std::min<std::uint64_t>(count, size - offset));
        stream.read(reinterpret_cast<char*>(buffer.data()), available);
        if (static_cast<std::size_t>(stream.gcount()) != available) {
            throw std::runtime_error("short read");
        }
    }

    int at(std::size_t index, std::uint64_t absolute) const {
        return absolute < size ? buffer[index] : -1;
    }
};

void print_metric(const char* name, const Metric& metric, bool print_runs) {
    std::cout << "  \"" << name << "\": {\"bytes\": " << metric.bytes
              << ", \"sectors\": " << metric.sectors.size()
              << ", \"runs\": " << metric.run_count;
    if (print_runs) {
        std::cout << ", \"first_ranges\": [";
        for (std::size_t i = 0; i < metric.first_runs.size(); ++i) {
            const auto& run = metric.first_runs[i];
            if (i) {
                std::cout << ", ";
            }
            std::cout << "[\"" << std::hex << "0x" << run.begin << "\", \"0x"
                      << run.end << "\", " << std::dec << run.end - run.begin
                      << "]";
        }
        std::cout << "]";
    }
    std::cout << "}";
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "usage: tweaks_diff_algebra B.bin T.bin S.bin TS.bin\n";
        return 2;
    }
    try {
        std::array<Input, 4> inputs{
            Input(argv[1]), Input(argv[2]), Input(argv[3]), Input(argv[4])};
        const auto total = std::max(
            std::max(inputs[0].size, inputs[1].size),
            std::max(inputs[2].size, inputs[3].size));

        Metric title, script, combined, overlap, mismatch;
        Metric user_title, user_script, user_combined;
        Metric conflicting_overlap, user_overlap, user_conflicting_overlap;
        Metric user_mismatch;
        std::uint64_t title_context_mismatch = 0;
        std::uint64_t script_context_mismatch = 0;
        for (std::uint64_t base = 0; base < total; base += kBufferSize) {
            const auto count = static_cast<std::size_t>(
                std::min<std::uint64_t>(kBufferSize, total - base));
            for (auto& input : inputs) {
                input.read(base, count);
            }
            for (std::size_t i = 0; i < count; ++i) {
                const auto offset = base + i;
                const int b = inputs[0].at(i, offset);
                const int t = inputs[1].at(i, offset);
                const int s = inputs[2].at(i, offset);
                const int ts = inputs[3].at(i, offset);
                const bool dt = t != b;
                const bool ds = s != b;
                const bool dts = ts != b;
                if (dt) title.mark(offset);
                if (ds) script.mark(offset);
                if (dts) combined.mark(offset);
                if (dt && ds) overlap.mark(offset);
                if (dt && ds && t != s) conflicting_overlap.mark(offset);
                const int expected = dt ? t : s;
                if (ts != expected) mismatch.mark(offset);
                const auto sector_offset = offset % kRawSectorSize;
                const bool user_data =
                    sector_offset >= 24 && sector_offset < 24 + 2048;
                if (user_data && dt) user_title.mark(offset);
                if (user_data && ds) user_script.mark(offset);
                if (user_data && dts) user_combined.mark(offset);
                if (user_data && dt && ds) user_overlap.mark(offset);
                if (user_data && dt && ds && t != s) {
                    user_conflicting_overlap.mark(offset);
                }
                if (user_data && ts != expected) user_mismatch.mark(offset);
                if (dt && ts != t) ++title_context_mismatch;
                if (ds && !dt && ts != s) ++script_context_mismatch;
            }
        }
        for (Metric* metric : {&title, &script, &combined, &overlap, &mismatch,
                               &user_title, &user_script, &user_combined,
                               &conflicting_overlap, &user_overlap,
                               &user_conflicting_overlap, &user_mismatch}) {
            metric->finish();
        }

        std::cout << "{\n";
        std::cout << "  \"sizes\": [" << inputs[0].size << ", " << inputs[1].size
                  << ", " << inputs[2].size << ", " << inputs[3].size << "],\n";
        print_metric("title_delta", title, true); std::cout << ",\n";
        print_metric("script_delta", script, false); std::cout << ",\n";
        print_metric("combined_delta", combined, false); std::cout << ",\n";
        print_metric("user_title_delta", user_title, false); std::cout << ",\n";
        print_metric("user_script_delta", user_script, false); std::cout << ",\n";
        print_metric("user_combined_delta", user_combined, false); std::cout << ",\n";
        print_metric("overlap", overlap, true); std::cout << ",\n";
        print_metric("conflicting_overlap", conflicting_overlap, true);
        std::cout << ",\n";
        print_metric("compose_mismatch", mismatch, true); std::cout << ",\n";
        print_metric("user_overlap", user_overlap, true); std::cout << ",\n";
        print_metric("user_conflicting_overlap", user_conflicting_overlap, true);
        std::cout << ",\n";
        print_metric("user_compose_mismatch", user_mismatch, true);
        std::cout << ",\n";
        std::cout << "  \"title_context_mismatch\": " << title_context_mismatch
                  << ",\n";
        std::cout << "  \"script_context_mismatch\": " << script_context_mismatch
                  << "\n}\n";
        return user_mismatch.bytes == 0 ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
