#ifndef GTXASIO_PROTOCOL_H
#define GTXASIO_PROTOCOL_H
#include <stdint.h>
#define GTX_MAGIC UINT32_C(0x31585447) /* "GTX1" on little endian */
#define GTX_VERSION 1u
#define GTX_PORT 37261
#define GTX_CHANNELS 2u
#define GTX_MAX_FRAMES 1024u
#define GTX_PACKET_HEADER 24u
/* Fixed-width LE header. Both processes are x86-64 little-endian. */
#pragma pack(push,1)
typedef struct {
    uint32_t magic, version, sequence, frames, rate, status;
    float audio[GTX_CHANNELS * GTX_MAX_FRAMES]; /* interleaved stereo float32 */
} GTXPacket;
#pragma pack(pop)
#define GTX_PACKET_SIZE(frames) (GTX_PACKET_HEADER + sizeof(float)*GTX_CHANNELS*(frames))
#endif
