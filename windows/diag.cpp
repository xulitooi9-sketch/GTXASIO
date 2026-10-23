/* GTXASIO v0.1.3: Wine/COM sample-rate diagnostic (no real audio opened).
 * This is intentionally a small ABI-specific smoke test, not an ASIO SDK client.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <cstdio>
#include <cstring>
#include <initializer_list>

/* First portion of GTXASIO's 64-bit ASIO-compatible COM vtable. */
class IGTXASIO : public IUnknown {
public:
  virtual LONG Init(void *sysRef) = 0;
  virtual void GetDriverName(char *name) = 0;
  virtual LONG GetDriverVersion() = 0;
  virtual void GetErrorMessage(char *message) = 0;
  virtual LONG Start() = 0;
  virtual LONG Stop() = 0;
  virtual LONG GetChannels(LONG *inputs, LONG *outputs) = 0;
  virtual LONG GetLatencies(LONG *inputs, LONG *outputs) = 0;
  virtual LONG GetBufferSize(LONG *min, LONG *max, LONG *preferred, LONG *granularity) = 0;
  virtual LONG CanSampleRate(double sampleRate) = 0;
  virtual LONG GetSampleRate(double *sampleRate) = 0;
  virtual LONG SetSampleRate(double sampleRate) = 0;
};
int main() {
  const GUID clsid={0x6e63c705,0xa578,0x4b65,{0x8a,0x24,0xa8,0x13,0xb2,0xe4,0xb1,0xa0}};
  HRESULT hr=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
  if (FAILED(hr)) { std::printf("COM init failed: 0x%08lx\n",static_cast<unsigned long>(hr)); return 2; }
  IUnknown *unknown=nullptr;
  hr=CoCreateInstance(clsid,nullptr,CLSCTX_INPROC_SERVER,IID_IUnknown,reinterpret_cast<void**>(&unknown));
  if (FAILED(hr) || !unknown) {
    std::printf("CoCreateInstance failed: 0x%08lx (check WINEPREFIX and DLL registration)\n",static_cast<unsigned long>(hr));
    CoUninitialize();return 3;
  }
  auto *driver=reinterpret_cast<IGTXASIO*>(unknown);
  char name[64]={0};
  const LONG initialized=driver->Init(nullptr);
  driver->GetDriverName(name);
  std::printf("Driver: %s, init=%ld, version=%ld\n",name,(long)initialized,(long)driver->GetDriverVersion());
  bool ok=initialized!=0 && std::strcmp(name,"GTXASIO")==0;
  for (double rate: {44100.0,48000.0}) {
    const LONG can=driver->CanSampleRate(rate);
    const LONG set=driver->SetSampleRate(rate);
    double got=0;const LONG get=driver->GetSampleRate(&got);
    std::printf("rate %.0f: Can=%ld, Set=%ld, Get=%ld, current=%.0f\n",rate,(long)can,(long)set,(long)get,got);
    if (can!=0 || set!=0 || get!=0 || got!=rate) ok=false;
  }
  LONG inputs=0,outputs=0,minimum=0,maximum=0,preferred=0,granularity=0;
  const LONG ch=driver->GetChannels(&inputs,&outputs);
  const LONG bs=driver->GetBufferSize(&minimum,&maximum,&preferred,&granularity);
  std::printf("channels: rc=%ld, %ld input/%ld output; buffer: rc=%ld preferred=%ld\n",(long)ch,(long)inputs,(long)outputs,(long)bs,(long)preferred);
  if (ch!=0||bs!=0||inputs!=2||outputs!=2||preferred<=0) ok=false;
  unknown->Release();CoUninitialize();
  std::printf("GTXASIO Wine probe: %s\n",ok?"OK":"FAILED");
  return ok?0:4;
}
