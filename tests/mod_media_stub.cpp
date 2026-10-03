#include "mod_media.h"

// Catalog unit tests contain no donor ROMs. Unexpected media resolution should
// fail explicitly instead of depending on the developer's private files.
namespace PSXRecompV4 {
bool load_mod_media(const std::filesystem::path&, const std::string&, uint64_t,
                    const std::string&,
                    std::shared_ptr<const std::vector<uint8_t>>&,
                    std::string* error) {
    if (error) *error = "donor media is outside this catalog test";
    return false;
}
}
