/* GTXASIO experimental Linux audio engine. No dependency on PipeASIO/JACK.
 * MIT license; see LICENSE. ALSA is dynamically loaded so it compiles even
 * when libasound development headers are not installed.
 */
#define _POSIX_C_SOURCE 200809L
#include "../common/protocol.h"
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

typedef struct _snd_pcm snd_pcm_t;
typedef unsigned long pcm_frames_t;
typedef long pcm_sframes_t;
typedef struct {
  void *dl;
  int (*open)(snd_pcm_t **, const char *, int, int);
  int (*close)(snd_pcm_t *);
  int (*set_params)(snd_pcm_t *, int, int, unsigned, unsigned, int, unsigned);
  pcm_sframes_t (*writei)(snd_pcm_t *, const void *, pcm_frames_t);
  pcm_sframes_t (*readi)(snd_pcm_t *, void *, pcm_frames_t);
  int (*recover)(snd_pcm_t *, int, int);
  int (*nonblock)(snd_pcm_t *, int);
  const char *(*strerror)(int);
} Alsa;
static Alsa a;
static volatile sig_atomic_t running = 1;
static void quit(int x) { (void)x; running = 0; }

#define LOAD(x, symbol) do { *(void **)(&a.x) = dlsym(a.dl, "snd_pcm_" symbol); \
  if (!a.x) { fprintf(stderr,"GTXASIO: missing ALSA function %s\n", symbol); return -1; } } while(0)
static int load_alsa(void) {
  a.dl = dlopen("libasound.so.2", RTLD_NOW | RTLD_LOCAL);
  if (!a.dl) { fprintf(stderr,"GTXASIO: cannot load libasound.so.2: %s\n", dlerror()); return -1; }
  LOAD(open,"open"); LOAD(close,"close"); LOAD(set_params,"set_params");
  LOAD(writei,"writei"); LOAD(readi,"readi"); LOAD(recover,"recover");
  LOAD(nonblock,"nonblock");
  *(void **)(&a.strerror) = dlsym(a.dl, "snd_strerror");
  return a.strerror ? 0 : -1;
}
#undef LOAD

#define RING_FRAMES 16384u
static struct {
  pthread_mutex_t mu;
  snd_pcm_t *pcm;
  float ring[RING_FRAMES * 2];
  uint64_t read_pos, write_pos;
  _Atomic uint64_t xruns;
  _Atomic unsigned peak_milli; /* Last report-window peak, 0..1000. */
  unsigned channels; /* 1 for mono microphone, 2 for stereo. */
  unsigned chunk_frames; /* Keep capture reads aligned with selected ASIO buffer. */
  int enabled;
} mic = { .mu = PTHREAD_MUTEX_INITIALIZER };

static void *capture_thread(void *x) {
  (void)x;
  float block[GTX_MAX_FRAMES*2];
  while (running) {
    /* Some virtual ALSA capture devices do not fill all returned frames. */
    memset(block, 0, sizeof(block));
    pcm_sframes_t n = a.readi(mic.pcm, block, mic.chunk_frames);
    if (n < 0) {
      if (n == -EAGAIN || n == -EINTR) { struct timespec ts = {0,1000000}; nanosleep(&ts,NULL); continue; }
      atomic_fetch_add(&mic.xruns,1);
      if (a.recover(mic.pcm, (int)n, 1) < 0) { struct timespec ts = {0,10000000}; nanosleep(&ts,NULL); }
      continue;
    }
    if (n == 0) { struct timespec ts = {0,1000000}; nanosleep(&ts,NULL); continue; }
    /* Accept mono capture hardware too. Replicate mono to ASIO inputs L/R. */
    unsigned peak = 0;
    pthread_mutex_lock(&mic.mu);
    for (pcm_sframes_t i=0; i<n; ++i) {
      const float left = block[(size_t)i * mic.channels];
      const float right = mic.channels == 2 ? block[(size_t)i * 2 + 1] : left;
      const float magn = fmaxf(fabsf(left), fabsf(right));
      if (isfinite(magn)) {
        const unsigned v = magn >= 1.0f ? 1000u : (unsigned)(magn * 1000.0f);
        if (v > peak) peak = v;
      }
      unsigned j = (unsigned)(mic.write_pos % RING_FRAMES);
      mic.ring[j*2] = isfinite(left) ? left : 0.0f;
      mic.ring[j*2+1] = isfinite(right) ? right : 0.0f;
      mic.write_pos++;
    }
    unsigned old = atomic_load(&mic.peak_milli);
    while (old < peak && !atomic_compare_exchange_weak(&mic.peak_milli, &old, peak)) {}

    if (mic.write_pos - mic.read_pos > RING_FRAMES)
      mic.read_pos = mic.write_pos - RING_FRAMES;
    pthread_mutex_unlock(&mic.mu);
    /* Avoid a busy loop with virtual ALSA capture devices such as null. */
    { struct timespec ts = {0,1000000}; nanosleep(&ts,NULL); }
  }
  return NULL;
}
static void fetch_capture(float *out, unsigned frames) {
  memset(out,0,frames*2*sizeof(float));
  if (!mic.enabled) return;
  pthread_mutex_lock(&mic.mu);
  uint64_t available = mic.write_pos - mic.read_pos;
  if (available > frames * 4u) mic.read_pos = mic.write_pos - frames; /* drift control */
  for (unsigned i=0; i<frames && mic.read_pos<mic.write_pos; ++i) {
    unsigned j = (unsigned)(mic.read_pos++ % RING_FRAMES);
    out[2*i]=mic.ring[2*j]; out[2*i+1]=mic.ring[2*j+1];
  }
  pthread_mutex_unlock(&mic.mu);
}
static uint64_t mono_ns(void) {
  struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}
static void pace_until(uint64_t ns) {
  struct timespec ts = { (time_t)(ns/1000000000ull), (long)(ns%1000000000ull) };
  while (running && clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&ts,NULL)==EINTR) {}
}
static int set_pcm(snd_pcm_t **pcm, const char *name, int stream, unsigned rate, unsigned frames, unsigned *actual_channels) {
  int rc = a.open(pcm,name,stream,0);
  if (rc < 0) { fprintf(stderr,"GTXASIO: failed to open %s: %s\n",name,a.strerror(rc)); return -1; }
  /* ALSA enum: FLOAT_LE=14, RW_INTERLEAVED=3. 2 channels. */
  unsigned latency_us = (unsigned)((uint64_t)frames*1000000ull/rate*4);
  /* v0.1.4 forced 20 ms even at 64 frames. Lower this to 6 ms for
     low-latency buffers; ALSA can choose larger actual hardware periods. */
  if (latency_us < 6000) latency_us = 6000;
  rc = a.set_params(*pcm,14,3,2,rate,1,latency_us);
  if (rc == 0) { if (actual_channels) *actual_channels = 2; return 0; }
  if (stream == 1) {
    /* Capture devices like laptop internal microphones are often mono.
       Keep the two ASIO inputs by duplicating the mono signal into L/R. */
    rc = a.set_params(*pcm,14,3,1,rate,1,latency_us);
    if (rc == 0) {
      if (actual_channels) *actual_channels = 1;
      fprintf(stderr,"GTXASIO: microphone is mono; duplicating signal to ASIO inputs 1/2\n");
      return 0;
    }
  }
  fprintf(stderr,"GTXASIO: %s cannot open %u Hz float audio: %s\n",name,rate,a.strerror(rc));
  a.close(*pcm); *pcm=NULL; return -1;
}
static int put_audio(snd_pcm_t *pcm, const float *samples, unsigned frames, uint64_t *xruns) {
  unsigned sent=0;
  while (sent<frames && running) {
    pcm_sframes_t rc = a.writei(pcm,samples+(size_t)sent*2,frames-sent);
    if (rc<0) {
      if (rc == -EINTR) continue;
      ++*xruns;
      if (a.recover(pcm,(int)rc,1)<0) return -1;
      continue;
    }
    if (rc==0) return -1;
    sent += (unsigned)rc;
  }
  return sent==frames ? 0 : -1;
}
static int parse_uint(const char *s, unsigned *val) {
  char *end; unsigned long n = strtoul(s,&end,10);
  if (!*s || *end || n>1000000) return -1;
  *val = (unsigned)n; return 0;
}
int main(int argc, char **argv) {
  const char *outdev="default", *indev="default";
  unsigned rate=48000, frames=512;
  int input_enabled=1;
  for (int i=1;i<argc;++i) {
    if (!strcmp(argv[i],"--output") && i+1<argc) outdev=argv[++i];
    else if (!strcmp(argv[i],"--input") && i+1<argc) indev=argv[++i];
    else if (!strcmp(argv[i],"--rate") && i+1<argc && parse_uint(argv[++i],&rate)==0) {}
    else if (!strcmp(argv[i],"--buffer") && i+1<argc && parse_uint(argv[++i],&frames)==0) {}
    else if (!strcmp(argv[i],"--no-input")) input_enabled=0;
    else { fprintf(stderr,"Usage: %s [--output default|null|plughw:N,M] [--input default] [--no-input] [--rate 44100|48000] [--buffer 64|128|256|512|1024]\n",argv[0]); return 2; }
  }
  if ((rate!=44100 && rate!=48000) || (frames!=64 && frames!=128 && frames!=256 && frames!=512 && frames!=1024)) {
    fprintf(stderr,"GTXASIO: unsupported rate or buffer size\n"); return 2;
  }
  if (load_alsa()<0) return 1;
  signal(SIGINT,quit); signal(SIGTERM,quit);
  snd_pcm_t *playback=NULL;
  if (set_pcm(&playback,outdev,0,rate,frames,NULL)<0) return 1;
  pthread_t cap_tid; int cap_started=0;
  if (input_enabled) {
    if (set_pcm(&mic.pcm,indev,1,rate,frames,&mic.channels)==0) {
      a.nonblock(mic.pcm,1); mic.chunk_frames=frames; mic.enabled=1;
      if (pthread_create(&cap_tid,NULL,capture_thread,NULL)==0) cap_started=1;
      else { mic.enabled=0; a.close(mic.pcm); mic.pcm=NULL; }
    } else fprintf(stderr,"GTXASIO: capture disabled; sending silence (check --input device and microphone permissions)\n");
  }
  /* In automatic mode systemd owns UDP port 37261 and passes its socket
   * as descriptor 3 (LISTEN_FDS=1). Manual mode can still bind normally. */
  int sock=-1, socket_activated=0;
  const char *fds=getenv("LISTEN_FDS"), *pid=getenv("LISTEN_PID");
  if (fds && pid && strcmp(fds,"1")==0 && (pid_t)strtol(pid,NULL,10)==getpid()) {
    struct sockaddr_in inherited={0}; socklen_t len=sizeof(inherited);
    int type=0; socklen_t type_len=sizeof(type);
    if(getsockname(3,(struct sockaddr *)&inherited,&len)==0 &&
       getsockopt(3,SOL_SOCKET,SO_TYPE,&type,&type_len)==0 &&
       type==SOCK_DGRAM && inherited.sin_family==AF_INET &&
       inherited.sin_port==htons(GTX_PORT) &&
       inherited.sin_addr.s_addr==htonl(INADDR_LOOPBACK)) {
      sock=3; socket_activated=1;
    } else {
      fprintf(stderr,"GTXASIO: invalid socket-activation descriptor 3\n"); return 1;
    }
    unsetenv("LISTEN_FDS"); unsetenv("LISTEN_PID");
  }
  if(sock<0) {
    sock = socket(AF_INET,SOCK_DGRAM,0);
    if (sock<0) { perror("socket"); return 1; }
    struct sockaddr_in addr={0}; addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK); addr.sin_port=htons(GTX_PORT);
    if (bind(sock,(struct sockaddr *)&addr,sizeof(addr))<0) { perror("bind 127.0.0.1:37261"); close(sock); return 1; }
  }
  struct timeval wait={.tv_sec=0,.tv_usec=200000};
  setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,&wait,sizeof(wait));
  printf("GTXASIO engine v0.1.7: %u Hz, %u frames, out=%s, in=%s (%s), UDP localhost:%d\n",rate,frames,outdev,indev,mic.enabled?"on":"silence",GTX_PORT);
  fflush(stdout);
  GTXPacket *rx = calloc(1,sizeof(GTXPacket)), *tx=calloc(1,sizeof(GTXPacket));
  if (!rx || !tx) return 1;
  uint64_t next_tick=0, xout=0, requests=0, bad=0, previous_ns=0;
  uint64_t last_packet_ns=mono_ns();
  const uint64_t idle_ns=3ull*1000000000ull;
  while (running) {
    struct sockaddr_in peer={0}; socklen_t plen=sizeof(peer);
    ssize_t n=recvfrom(sock,rx,sizeof(*rx),0,(struct sockaddr*)&peer,&plen);
    if (n<0) {
      if (errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR) {
        next_tick=0;
        if(socket_activated && mono_ns()-last_packet_ns>=idle_ns) {
          fprintf(stderr,"GTXASIO: idle; releasing mic and output. Ready for next activation.\n");
          break;
        }
        continue;
      }
      perror("recvfrom"); break;
    }
    if (peer.sin_addr.s_addr!=htonl(INADDR_LOOPBACK) || n<(ssize_t)GTX_PACKET_HEADER || rx->magic!=GTX_MAGIC || rx->version!=GTX_VERSION || rx->frames!=frames || rx->rate!=rate || (size_t)n!=GTX_PACKET_SIZE(frames)) {
      bad++; continue;
    }
    /* Clip pathological samples from buggy plugins, suppress NaN and Infinity. */
    for (unsigned i=0;i<frames*2;i++) {
      float x=rx->audio[i];
      if (!isfinite(x)) x=0.0f;
      rx->audio[i] = x < -1.0f ? -1.0f : x > 1.0f ? 1.0f : x;
    }
    last_packet_ns=mono_ns();
    int ok=put_audio(playback,rx->audio,frames,&xout);
    tx->magic=GTX_MAGIC;tx->version=GTX_VERSION;tx->sequence=rx->sequence;tx->rate=rate;tx->frames=frames;
    tx->status=ok==0 ? 0u : 1u;
    fetch_capture(tx->audio,frames);
    uint64_t now=mono_ns();
    uint64_t period=(uint64_t)frames*1000000000ull/rate;
    if (!next_tick || now>next_tick+period*2) next_tick=now+period;
    else next_tick+=period;
    if (next_tick>now) pace_until(next_tick);
    sendto(sock,tx,GTX_PACKET_SIZE(frames),0,(struct sockaddr*)&peer,plen);
    requests++;
    if (!previous_ns) previous_ns=now;
    if (now-previous_ns>=5000000000ull) {
      unsigned peak = atomic_exchange(&mic.peak_milli,0);
      fprintf(stderr,"GTXASIO: blocks=%llu playback_recoveries=%llu capture_recoveries=%llu invalid=%llu mic_peak=%.1f%% (%s)\n",
        (unsigned long long)requests,(unsigned long long)xout,(unsigned long long)atomic_load(&mic.xruns),(unsigned long long)bad,peak/10.0,mic.enabled?"on":"off");
      previous_ns=now;
    }
  }
  close(sock); running=0;
  if (cap_started) pthread_join(cap_tid,NULL);
  if (mic.pcm) a.close(mic.pcm);
  if (playback) a.close(playback);
  free(rx); free(tx);
  return 0;
}
