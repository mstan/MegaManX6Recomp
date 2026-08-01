#include "mod_packages.h"

#include <filesystem>
#include <iostream>
#include <string>

namespace {

constexpr size_t kExpectedPackages = 14;
constexpr size_t kExpectedFeatures = 201;
constexpr size_t kExpectedTweaksPackages = 12;
constexpr const char* kGameId = "SLUS-01395";
constexpr const char* kStockDiscSha256 =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

int fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    return 1;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) return fail("expected the preloaded mods root");

    const std::filesystem::path root(argv[1]);
    size_t manifest_count = 0;
    for (const std::filesystem::directory_entry& entry :
         std::filesystem::recursive_directory_iterator(root / "packages")) {
        if (!entry.is_regular_file() ||
            entry.path().filename() != "manifest.toml") {
            continue;
        }
        ++manifest_count;
        PSXRecompV4::ModPackage package;
        std::string parse_error;
        if (!PSXRecompV4::ModPackageManager::read_manifest(
                entry.path(), package, &parse_error)) {
            return fail("manifest parse failed: " + parse_error);
        }
    }
    if (manifest_count != kExpectedPackages) {
        return fail("expected " + std::to_string(kExpectedPackages) +
                    " manifests, found " + std::to_string(manifest_count));
    }

    PSXRecompV4::ModPackageManager manager{root};
    std::string error;
    if (!manager.scan(&error)) return fail("catalog scan failed: " + error);
    if (!manager.load_state(&error)) return fail("default state failed: " + error);

    if (manager.packages().size() != kExpectedPackages) {
        return fail("expected " + std::to_string(kExpectedPackages) +
                    " package families, found " +
                    std::to_string(manager.packages().size()));
    }

    size_t feature_count = 0;
    size_t linked_tweaks_packages = 0;
    for (const auto& [id, versions] : manager.packages()) {
        if (versions.size() != 1) {
            return fail(id + " must preload exactly one package version");
        }
        const PSXRecompV4::ModPackage* package = manager.selected_package(id);
        if (!package) return fail(id + " has no selected package version");
        if (id == "mmx6.tweaks.assets" ||
            id == "mmx6.tweaks.extra-mugshots" ||
            id == "mmx6.tweaks.ingame-options") {
            return fail(id + " is permission-gated and must remain withheld");
        }
        if (id.rfind("mmx6.tweaks.", 0) == 0) {
            ++linked_tweaks_packages;
            if (package->source_name != "Mega Man X6 Tweaks" ||
                package->source_url !=
                    "https://www.romhacking.net/hacks/4035/") {
                return fail(id + " is missing its MMX6 Tweaks source link");
            }
            if (package->author_links.empty() ||
                package->author_links[0].name != "acediez" ||
                package->author_links[0].url !=
                    "https://twitter.com/acediez") {
                return fail(id + " has incomplete linked author metadata");
            }
            for (const auto& link : package->author_links) {
                if (link.name == "NectarHime") {
                    return fail(id + " incorrectly credits NectarHime");
                }
            }
            if (package->author_links.size() != 1u) {
                return fail(id + " has incorrectly scoped author links");
            }
        }
        feature_count += package->features.size();
        for (const PSXRecompV4::ModFeature& feature : package->features) {
            const std::string& displayed_author =
                feature.author.empty() ? package->author : feature.author;
            if (displayed_author.find("PSXRecomp") != std::string::npos) {
                return fail(id + "/" + feature.id +
                            " exposes implementation attribution");
            }
            if (displayed_author.find("NectarHime") != std::string::npos) {
                return fail(id + "/" + feature.id +
                            " incorrectly credits NectarHime");
            }
            const bool retranslation =
                id == "mmx6.tweaks.native" &&
                feature.id == "retranslation";
            if (retranslation) {
                return fail("retranslation must remain withheld");
            }
            if (displayed_author.find("DuoDynamo") != std::string::npos ||
                displayed_author.find("Metalwario64") != std::string::npos) {
                return fail(id + "/" + feature.id +
                            " exposes permission-gated collaborator content");
            }
            if (feature.default_enabled) {
                return fail(id + "/" + feature.id + " is enabled by default");
            }
        }
    }
    if (feature_count != kExpectedFeatures) {
        return fail("expected " + std::to_string(kExpectedFeatures) +
                    " features, found " + std::to_string(feature_count));
    }
    if (linked_tweaks_packages != kExpectedTweaksPackages) {
        return fail("expected " + std::to_string(kExpectedTweaksPackages) +
                    " linked Tweaks packages, found " +
                    std::to_string(linked_tweaks_packages));
    }
    if (std::filesystem::exists(
            root / "packages" / "mmx6.tweaks.native" / "1.10.5" /
            "assets" / "retranslation")) {
        return fail("retranslation payload must remain withheld");
    }

    for (const auto& [package_id, selection] : manager.selections()) {
        if (selection.enabled) {
            return fail(package_id + " legacy package state is enabled");
        }
        for (const auto& [feature_id, feature] : selection.features) {
            if (feature.enabled) {
                return fail(package_id + "/" + feature_id +
                            " resolved enabled in the default state");
            }
        }
    }

    const PSXRecompV4::ModResolution plan =
        manager.resolve(kGameId, "", kStockDiscSha256);
    if (!plan.ok) {
        std::string detail;
        for (const std::string& item : plan.errors) {
            if (!detail.empty()) detail += "; ";
            detail += item;
        }
        return fail("default catalog resolution failed: " + detail);
    }
    if (!plan.writes.empty() || !plan.overlays.empty() ||
        !plan.derived_discs.empty()) {
        return fail("default-disabled catalog produced runtime operations");
    }

    std::cout << "preloaded mods: " << manager.packages().size()
              << " packages, " << feature_count
              << " default-disabled features\n";
    return 0;
}
