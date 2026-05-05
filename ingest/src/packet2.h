/* packet2.h - Meridian field telemetry packet format, version 2.
 *
 * The 2008 "MRD1" frame (see packet.h) has six channels and has not
 * changed since the loggers were first deployed.  The 2026 logger
 * refresh adds two agronomy channels the old frame had no room for: a
 * soil temperature probe (SOILT) and a leaf wetness sensor (LEAFWET).
 * Rather than disturb the frozen MRD1 layout -- every tool downstream
 * knows it to the byte -- the new firmware emits a wider "MRD2" frame
 * and stamps it with its own magic, so a collector can tell the two
 * apart on the wire and decode each with the right reader.
 *
 * MRD2 is strictly additive: it is only ever produced by refreshed
 * loggers, and a frame is MRD2 only when its leading magic says so.
 * Fleets that have not been refreshed keep sending MRD1, which stays
 * the default everywhere.
 *
 * The wire is still big-endian, the CRC is still CRC16-CCITT (the very
 * same mrd_crc16 routine from packet.c, poly 0x1021, init 0xFFFF), and
 * channel ordering is again positional and baked into firmware.
 *
 * 2026-03.  Sits beside packet.h; it does not redefine anything MRD1.
 */
#ifndef MERIDIAN_PACKET2_H
#define MERIDIAN_PACKET2_H

#include <stdint.h>
#include <stddef.h>
#include "packet.h"   /* MRD_STNID_LEN, mrd_crc16, mrd_scale, flag bits */

#define MRD2_MAGIC         0x4D524432u   /* "MRD2" */
#define MRD2_PACKET_BYTES  52
#define MRD2_MAX_CHANNELS  8
#define MRD2_FORMAT_VERSION 2            /* value carried in the version byte */

/* Byte offsets of the MRD2 wire frame (big-endian throughout):
 *   0  u32 magic   = 0x4D524432 ("MRD2")
 *   4  char stnid[8]            (space padded, NOT nul terminated)
 *   12 u16 year
 *   14 u16 doy
 *   16 i32 value[8]            scaled x100, channels below
 *   48 u8  version             format version byte (= MRD2_FORMAT_VERSION)
 *   49 u8  flags               0x01 suspect, 0x02 manual
 *   50 u16 crc16               CCITT over the extended region, bytes 0..49
 * Total 52 bytes.  The CRC region is "extended" relative to MRD1: it
 * covers the eight channels, the version byte and the flags byte, i.e.
 * everything ahead of the trailing CRC. */
#define MRD2_OFF_MAGIC    0
#define MRD2_OFF_STNID    4
#define MRD2_OFF_YEAR     12
#define MRD2_OFF_DOY      14
#define MRD2_OFF_VALUES   16
#define MRD2_OFF_VERSION  48
#define MRD2_OFF_FLAGS    49
#define MRD2_OFF_CRC      50

/* Number of frame bytes the CRC is meant to protect: everything up to
 * but not including the trailing u16 CRC itself (bytes 0..49). */
#define MRD2_CRC_LEN      50

/* Channel ordering.  The first six match MRD1 one-for-one so shared
 * code can treat them the same; the two new ones follow. */
enum mrd2_channel {
    MRD2_CH_TMAX    = 0,
    MRD2_CH_TMIN    = 1,
    MRD2_CH_RAIN    = 2,
    MRD2_CH_SRAD    = 3,
    MRD2_CH_RH      = 4,
    MRD2_CH_WIND    = 5,
    MRD2_CH_SOILT   = 6,   /* soil temperature, deg C   */
    MRD2_CH_LEAFWET = 7    /* leaf wetness, percent     */
};

/* MRD2 reuses the MRD1 flag bit values so the suspect/manual meaning is
 * identical across formats; the field is only a byte wide here. */
#define MRD2_FLAG_SUSPECT 0x01u
#define MRD2_FLAG_MANUAL  0x02u

struct mrd2_packet {
    uint32_t magic;
    char     stnid[MRD_STNID_LEN];
    uint16_t year;
    uint16_t doy;
    int32_t  value[MRD2_MAX_CHANNELS];   /* scaled by 100, see mrd_scale */
    uint8_t  version;
    uint8_t  flags;
    uint16_t crc;
};

/* Parse a wire frame into out.  Returns 0 on success, or a negative
 * code matching mrd_packet_parse's convention so callers can share
 * attribution logic:
 *   -1 null pointer or short buffer
 *   -2 wrong magic (not an MRD2 frame)
 *   -3 CRC mismatch
 */
int mrd2_packet_parse(const unsigned char *buf, size_t len,
                      struct mrd2_packet *out);

/* Name of a channel, lower case, or "unknown". */
const char *mrd2_channel_name(int ch);

/* Peek the leading big-endian magic of a buffer without a full parse.
 * Returns the magic word, or 0 if the buffer is too short to hold one.
 * Handy for a reader that must decide MRD1 vs MRD2 before it knows how
 * many more bytes to pull. */
uint32_t mrd2_peek_magic(const unsigned char *buf, size_t len);

#endif
