# MegaManX6Recomp v1.0.9

v1.0.9 is a patch release for the bilinear texture filtering bug reported in
GitHub issue #20.

## Bilinear texture filtering

The OpenGL bilinear path no longer draws grid seams through the title-sequence
dialogue panel, portraits, and other textures assembled from small PS1 texture
rectangles.

The fix recenters the bilinear sample footprint on the same PS1 sampling grid
used by the renderer's primitive alignment, so 1x texture tiles sample their own
texels instead of blending against the previous row or column at tile
boundaries. Transparent cutout edges also keep the nearest texel as the
authority, which avoids dissolving sprite borders into transparent neighbours.

## Compatibility

Save files, memory cards and savestates from v1.0.8 continue to work. Your disc
image is unchanged and is still not included.
