// Isolated FBX decoder. Canonical output: metres, Z-up, world XYZW, sampled 30 fps.
#include <fbxsdk.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <stdexcept>

static void quote(std::ostream& out,const char* text) {
    out<<'"';for(const unsigned char c:std::string(text)) {
        if(c=='"'||c=='\\')out<<'\\'<<c;
        else if(c<32)out<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c)<<std::dec;
        else out<<c;
    }out<<'"';
}
static void transform(std::ostream& out,const FbxAMatrix& matrix) {
    auto scale=matrix.GetS();
    if(std::min({scale[0],scale[1],scale[2]})<=0||std::max({scale[0],scale[1],scale[2]})-std::min({scale[0],scale[1],scale[2]})>1e-4)
        throw std::runtime_error("Negative/non-uniform bone scale needs a clean exported skeleton");
    auto p=matrix.GetT();auto q=matrix.GetQ();q.Normalize();
    out<<'[';for(int i=0;i<7;i++) {
        double value=i<3?p[i]:q[i-3];if(!std::isfinite(value))throw std::runtime_error("Non-finite FBX transform");
        if(i)out<<',';out<<value;
    }out<<']';
}
static void gather(FbxNode* node,std::vector<FbxNode*>& nodes) {
    // Include transform parents as well as bones: skeleton roots need not be scene roots.
    nodes.push_back(node);for(int i=0;i<node->GetChildCount();i++)gather(node->GetChild(i),nodes);
}
int wmain(int argc,wchar_t** argv) {
    if(argc!=3){std::cerr<<"Usage: studio_fbx_read input.fbx output.json\n";return 2;}
    FbxManager* manager=nullptr;
    try {
        manager=FbxManager::Create();if(!manager)throw std::runtime_error("Cannot create FBX manager");
        manager->SetIOSettings(FbxIOSettings::Create(manager,IOSROOT));
        manager->GetIOSettings()->SetBoolProp(IMP_FBX_MATERIAL,false);
        manager->GetIOSettings()->SetBoolProp(IMP_FBX_TEXTURE,false);
        manager->GetIOSettings()->SetBoolProp(IMP_FBX_EXTRACT_EMBEDDED_DATA,false);
        auto scene=FbxScene::Create(manager,"StudioImport");auto importer=FbxImporter::Create(manager,"");
        auto input=std::filesystem::path(argv[1]).u8string();
        if(!importer->Initialize(input.c_str(),-1,manager->GetIOSettings()))throw std::runtime_error(importer->GetStatus().GetErrorString());
        auto extraction=std::filesystem::path(argv[2]).parent_path().u8string();importer->SetEmbeddingExtractionFolder(extraction.c_str());
        if(!importer->Import(scene))throw std::runtime_error(importer->GetStatus().GetErrorString());
        importer->Destroy();FbxAxisSystem::Max.ConvertScene(scene);FbxSystemUnit::m.ConvertScene(scene);
        std::vector<FbxNode*> all;gather(scene->GetRootNode(),all);std::vector<FbxNode*> nodes;
        // Keep bones and every ancestor, discard unrelated lights/geometry.
        std::map<FbxNode*,bool> keep;
        for(auto node:all)if(node->GetSkeleton())for(auto n=node;n;n=n->GetParent())keep[n]=true;
        for(auto node:all)if(keep[node])nodes.push_back(node);
        if(nodes.empty())throw std::runtime_error("No skeleton found in FBX");
        if(nodes.size()>4096)throw std::runtime_error("FBX contains too many skeleton nodes");
        const int stacks=scene->GetSrcObjectCount<FbxAnimStack>();
        if(stacks!=1)throw std::runtime_error("Select/export a single animation take before importing");
        auto stack=scene->GetSrcObject<FbxAnimStack>(0);scene->SetCurrentAnimationStack(stack);
        auto span=stack->GetLocalTimeSpan();double start=span.GetStart().GetSecondDouble(),end=span.GetStop().GetSecondDouble();
        if(!(std::isfinite(start)&&std::isfinite(end)&&end>start))throw std::runtime_error("FBX animation has no valid time range");
        const auto mode=scene->GetGlobalSettings().GetTimeMode();
        const double fps=mode==FbxTime::eCustom?scene->GetGlobalSettings().GetCustomFrameRate():FbxTime::GetFrameRate(mode);
        const size_t frames=size_t(std::ceil((end-start)*30.-1e-7))+1;
        // Bind matrices from skin clusters represent the authored reference pose.
        std::map<FbxNode*,FbxAMatrix> bind;
        for(auto node:all)if(auto mesh=node->GetMesh())for(int d=0;d<mesh->GetDeformerCount(FbxDeformer::eSkin);d++) {
            auto skin=static_cast<FbxSkin*>(mesh->GetDeformer(d,FbxDeformer::eSkin));
            for(int c=0;c<skin->GetClusterCount();c++){auto cluster=skin->GetCluster(c);if(cluster->GetLink()){FbxAMatrix matrix;cluster->GetTransformLinkMatrix(matrix);bind[cluster->GetLink()]=matrix;}}
        }
        for(int p=0;p<scene->GetPoseCount();p++) {
            auto pose=scene->GetPose(p);if(!pose->IsBindPose())continue;
            for(int j=0;j<pose->GetCount();j++)if(!pose->IsLocalMatrix(j)&&!bind.count(pose->GetNode(j))) {
                FbxAMatrix matrix;auto source=pose->GetMatrix(j);for(int row=0;row<4;row++)matrix.SetRow(row,source.GetRow(row));
                bind[pose->GetNode(j)]=matrix;
            }
        }
        std::ofstream out(std::filesystem::path(argv[2]),std::ios::binary);if(!out)throw std::runtime_error("Cannot open decoder output");out<<std::setprecision(17);
        out<<"{\"schema\":\"studio-external-world-v1\",\"source_fps\":"<<fps<<",\"fps\":30,\"duration\":"<<end-start<<",\"source_start\":"<<start<<",\"take\":";quote(out,stack->GetName());out<<",\"names\":[";
        std::map<FbxNode*,int> index;for(size_t j=0;j<nodes.size();j++){index[nodes[j]]=int(j);if(j)out<<',';quote(out,nodes[j]->GetName());}
        out<<"],\"parents\":[";for(size_t j=0;j<nodes.size();j++){if(j)out<<',';auto parent=nodes[j]->GetParent();out<<(index.count(parent)?index[parent]:-1);}
        out<<"],\"rest\":[";bool complete=true;
        for(size_t j=0;j<nodes.size();j++){if(j)out<<',';auto node=nodes[j];if(node->GetSkeleton()&&!bind.count(node))complete=false;transform(out,bind.count(node)?bind[node]:node->EvaluateGlobalTransform(FBXSDK_TIME_INFINITE));}
        out<<"],\"bind_complete\":"<<(complete?"true":"false")<<",\"world\":[";
        for(size_t f=0;f<frames;f++){if(f)out<<',';out<<'[';FbxTime time;time.SetSecondDouble(start+std::min(double(f)/30.,end-start));for(size_t j=0;j<nodes.size();j++){if(j)out<<',';transform(out,nodes[j]->EvaluateGlobalTransform(time));}out<<']';}
        out<<"]}";out.close();if(!out)throw std::runtime_error("Decoder output failed");manager->Destroy();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';if(manager)manager->Destroy();return 1;}
}

// MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
