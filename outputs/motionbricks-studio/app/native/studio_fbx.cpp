// MotionBricks Studio Ti FBX exporter. Extension code: Apache-2.0.
// Autodesk FBX SDK is separately licensed; see licenses/Autodesk-FBX-SDK-2020.3.11-LICENSE.txt.
#include <fbxsdk.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <stdexcept>
#include <cstdint>
#include <cmath>

struct Reader {
    std::ifstream f;
    Reader(const std::filesystem::path& p):f(p,std::ios::binary) {if(!f)throw std::runtime_error("Cannot read export snapshot");}
    template<class T> T get(){T t;read(&t,1);return t;}
    template<class T> void read(T* p,size_t n){if(!f.read(reinterpret_cast<char*>(p),sizeof(T)*n))throw std::runtime_error("Truncated export snapshot");}
    std::string str(){auto n=get<uint32_t>();std::string s(n,'\0');read(s.data(),n);return s;}
    FbxAMatrix matrix(){double m[16];read(m,16);FbxAMatrix out;for(int i=0;i<4;i++)for(int j=0;j<4;j++)out[j][i]=m[i*4+j];return out;}
};

int wmain(int argc,wchar_t** argv) {
    FbxManager* manager=nullptr;
    try {
        if(argc!=3)throw std::runtime_error("Usage: studio_fbx.exe snapshot.bin output.fbx");
        Reader in{std::filesystem::path(argv[1])};
        if(in.get<uint32_t>()!=0x54494246)throw std::runtime_error("Invalid export snapshot");
        uint32_t count=in.get<uint32_t>(),frames=in.get<uint32_t>(),fps=in.get<uint32_t>(),meshes=in.get<uint32_t>();
        if(count<2||frames<1||fps!=30)throw std::runtime_error("Invalid animation dimensions");
        manager=FbxManager::Create();
        if(!manager)throw std::runtime_error("Cannot initialize FBX SDK");
        manager->SetIOSettings(FbxIOSettings::Create(manager,IOSROOT));
        auto scene=FbxScene::Create(manager,"MotionBricks Studio Ti");
        scene->GetGlobalSettings().SetAxisSystem(FbxAxisSystem::Max);
        scene->GetGlobalSettings().SetSystemUnit(FbxSystemUnit::m);
        scene->GetGlobalSettings().SetTimeMode(FbxTime::eFrames30);
        auto info=FbxDocumentInfo::Create(manager,"DocumentInfo");
        info->mTitle="MotionBricks Studio Ti";info->mAuthor="MotionBricks Studio Ti";
        info->Original_ApplicationVendor="MASATAKA";info->Original_ApplicationName="MotionBricks Studio Ti";
        scene->SetSceneInfo(info);
        auto armature=FbxNode::Create(scene,"Armature");scene->GetRootNode()->AddChild(armature);
        std::vector<FbxNode*> nodes;std::vector<FbxAMatrix> bind;std::vector<int32_t> parents;
        auto pose=FbxPose::Create(scene,"BindPose");pose->SetIsBindPose(true);FbxAMatrix armatureBind;pose->Add(armature,FbxMatrix(armatureBind));
        for(uint32_t i=0;i<count;i++) {
            auto name=in.str();auto parent=in.get<int32_t>();auto world=in.matrix();
            if(parent>=int32_t(i)||parent < -1)throw std::runtime_error("Invalid skeleton hierarchy");
            auto node=FbxNode::Create(scene,name.c_str());
            auto bone=FbxSkeleton::Create(scene,name.c_str());bone->SetSkeletonType(FbxSkeleton::eLimbNode);
            bone->Size.Set(5.);node->SetNodeAttribute(bone);node->SetRotationOrder(FbxNode::eSourcePivot,eEulerXYZ);
            (parent<0?armature:nodes[parent])->AddChild(node);
            FbxAMatrix local=parent<0?world:bind[parent].Inverse()*world;
            node->LclTranslation.Set(local.GetT());node->LclRotation.Set(local.GetR());node->LclScaling.Set(FbxDouble3(1,1,1));
            nodes.push_back(node);bind.push_back(world);parents.push_back(parent);
            pose->Add(node,FbxMatrix(world));
        }
        std::vector<double> animation(size_t(frames)*count*6);in.read(animation.data(),animation.size());
        auto stack=FbxAnimStack::Create(scene,"Motion");auto layer=FbxAnimLayer::Create(scene,"BaseLayer");stack->AddMember(layer);
        FbxTime start,end;start.SetFrame(1,FbxTime::eFrames30);end.SetFrame(frames,FbxTime::eFrames30);
        stack->SetLocalTimeSpan(FbxTimeSpan(start,end));scene->GetGlobalSettings().SetTimelineDefaultTimeSpan(FbxTimeSpan(start,end));
        const char* axes[]={FBXSDK_CURVENODE_COMPONENT_X,FBXSDK_CURVENODE_COMPONENT_Y,FBXSDK_CURVENODE_COMPONENT_Z};
        for(uint32_t i=0;i<count;i++)for(int channel=0;channel<6;channel++) {
            auto curve=channel<3?nodes[i]->LclTranslation.GetCurve(layer,axes[channel],true):nodes[i]->LclRotation.GetCurve(layer,axes[channel-3],true);
            curve->KeyModifyBegin();
            for(uint32_t frame=0;frame<frames;frame++) {
                FbxTime time;time.SetFrame(frame+1,FbxTime::eFrames30);int key=curve->KeyAdd(time);
                double value=animation[(size_t(frame)*count+i)*6+channel];
                if(!std::isfinite(value))throw std::runtime_error("Non-finite animation value");
                curve->KeySetValue(key,float(value));curve->KeySetInterpolation(key,FbxAnimCurveDef::eInterpolationLinear);
            }
            curve->KeyModifyEnd();
        }
        for(uint32_t k=0;k<meshes;k++) {
            auto nv=in.get<uint32_t>(),nt=in.get<uint32_t>(),ni=in.get<uint32_t>();
            auto name=std::string("SOMA_Mesh_")+std::to_string(k);
            auto mesh=FbxMesh::Create(scene,name.c_str());mesh->InitControlPoints(nv);
            for(uint32_t v=0;v<nv;v++){double p[3];in.read(p,3);mesh->SetControlPointAt(FbxVector4(p[0],p[1],p[2]),v);}
            for(uint32_t t=0;t<nt;t++){mesh->BeginPolygon();for(int j=0;j<3;j++){auto v=in.get<uint32_t>();if(v>=nv)throw std::runtime_error("Invalid mesh index");mesh->AddPolygon(v);}mesh->EndPolygon();}
            std::vector<int32_t> indices(size_t(nv)*ni);std::vector<double> weights(size_t(nv)*ni);in.read(indices.data(),indices.size());in.read(weights.data(),weights.size());
            auto node=FbxNode::Create(scene,name.c_str());node->SetNodeAttribute(mesh);scene->GetRootNode()->AddChild(node);
            auto skin=FbxSkin::Create(scene,"Skin");
            for(uint32_t j=1;j<count;j++) {
                auto cluster=FbxCluster::Create(scene,nodes[j]->GetName());cluster->SetLink(nodes[j]);cluster->SetLinkMode(FbxCluster::eNormalize);
                FbxAMatrix identity;cluster->SetTransformMatrix(identity);cluster->SetTransformLinkMatrix(bind[j]);
                bool used=false;
                for(uint32_t v=0;v<nv;v++)for(uint32_t n=0;n<ni;n++){size_t ix=size_t(v)*ni+n;if(indices[ix]==int(j-1)&&weights[ix]>0){cluster->AddControlPointIndex(v,weights[ix]);used=true;}}
                if(used)skin->AddCluster(cluster);else cluster->Destroy();
            }
            mesh->AddDeformer(skin);mesh->GenerateNormals(true,true,false);
            auto smoothing=mesh->CreateElementSmoothing();smoothing->SetMappingMode(FbxLayerElement::eByPolygon);smoothing->SetReferenceMode(FbxLayerElement::eDirect);
            for(uint32_t t=0;t<nt;t++)smoothing->GetDirectArray().Add(1);
            auto uv=mesh->CreateElementUV("PreviewUV");uv->SetMappingMode(FbxLayerElement::eByControlPoint);uv->SetReferenceMode(FbxLayerElement::eDirect);
            for(uint32_t v=0;v<nv;v++){auto p=mesh->GetControlPointAt(v);uv->GetDirectArray().Add(FbxVector2(p[0]+.5,p[2]*.5));}
            FbxAMatrix identity;pose->Add(node,FbxMatrix(identity));
        }
        scene->AddPose(pose);
        auto exporter=FbxExporter::Create(manager,"");
        auto u8=std::filesystem::path(argv[2]).u8string();std::string target(u8.begin(),u8.end());
        // Binary FBX 7.4 is widely supported by UE, Unity and DCC importers.
        if(!exporter->Initialize(target.c_str(),-1,manager->GetIOSettings()))throw std::runtime_error(exporter->GetStatus().GetErrorString());
        exporter->SetFileExportVersion(FBX_2014_00_COMPATIBLE);
        if(!exporter->Export(scene))throw std::runtime_error(exporter->GetStatus().GetErrorString());
        exporter->Destroy();manager->Destroy();std::cout<<"FBX export complete\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";if(manager)manager->Destroy();return 1;}
}

// MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
