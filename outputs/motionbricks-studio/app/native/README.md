# FBX exporter and reader

The Windows source release provides the C++ source and build recipe for these
optional helpers. To enable FBX import and export, install the Autodesk FBX SDK
and build both helpers from the Studio directory using the commands below.

`studio_fbx_read.exe` is the isolated native FBX import helper built from `studio_fbx_read.cpp` by the same CMake recipe. It uses the same Autodesk SDK and notices. It accepts one skeletal animation take and emits evaluated world transforms in metres/Z-up at 30 fps, source timing and bind transforms. It does not contain the humanoid retargeter; `studio_external_motion.py` validates mappings and creates review candidates. Input files are never modified. See `docs/EXTERNAL_MOTION_IMPORT_JA.md` for neutral-pose requirements and limitations.

`studio_fbx.exe` is a Windows x64 helper built from `studio_fbx.cpp`, statically linked to Autodesk FBX SDK 2020.3.11 and the MSVC runtime. It runs in an isolated background process. Source code for the extension is Apache-2.0. Autodesk code is separately licensed. Preserve the notices under `licenses/Autodesk-FBX-*` when distributing this application.

Build with Visual Studio 2022 C++ tools and CMake after acquiring the official SDK:

```powershell
cmake -S app/native -B work/fbx-build -A x64 -DFBX_SDK_ROOT="C:/path/to/FBX SDK/2020.3.11"
cmake --build work/fbx-build --config Release
```

Official SDK source: https://damassets.autodesk.net/content/dam/autodesk/www/files/fbx2020311_fbxsdk_vs2022_win.exe

Protocol: little endian; magic 0x54494246, node/frame/fps/mesh counts (uint32), each node's UTF-8 byte length/name, int32 parent and row-major float64 world bind matrix; float64 frame-major local translation XYZ and Euler XYZ degrees; each mesh's vertex/triangle/influence counts, float64 points, uint32 triangles, int32 joint indices (without the added RootMotion node), float64 weights. The helper only consumes snapshots created by `studio_export.py`. Input is private temporary data, not an external import format.

Output: binary FBX 7.4, meters, Z up, baked 30 fps keys, bind pose and normalized skin clusters, optional mesh, dedicated RootMotion. The `Armature` wrapper has no transform and is omitted as a bone by UE's conventional FBX importer.

## Autodesk attribution

This software contains Autodesk® FBX® code developed by Autodesk, Inc. Copyright 2019 Autodesk, Inc. All rights, reserved. Such code is provided “as is” and Autodesk, Inc. disclaims any and all warranties, whether express or implied, including without limitation the implied warranties of merchantability, fitness for a particular purpose or non-infringement of third party rights. In no event shall Autodesk, Inc. be liable for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of such code.
