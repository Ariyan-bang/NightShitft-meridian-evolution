/* packet2.c - wire decoding for the MRD2 (2026) telemetry frame.
 *
 * 2026-03.  Companion to packet.c.  The byte readers here are the same
 * big-endian helpers packet.c uses; they are repeated rather than
 * exported because packet.c kept them file-static and the frozen MRD1
 * translation unit is not something to reopen for this.  The checksum
 * is NOT repeated: MRD2 uses the one and only mrd_crc16 from packet.c,
 * so both formats share a single, audited CRC implementation.
 */
#define _POSIX_C_SOURCE 200809L

#include <string.h>
#include "packet2.h"

static uint32_t rd_u32(const unsigned char *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8)  | (uint32_t)p[3];
}

static uint16_t rd_u16(const unsigned char *p)
{
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}

static int32_t rd_i32(const unsigned char *p)
{
    return (int32_t)rd_u32(p);
}

const char *mrd2_channel_name(int ch)
{
    switch (ch) {
    case MRD2_CH_TMAX:    return "tmax";
    case MRD2_CH_TMIN:    return "tmin";
    case MRD2_CH_RAIN:    return "rain";
    case MRD2_CH_SRAD:    return "srad";
    case MRD2_CH_RH:      return "rh";
    case MRD2_CH_WIND:    return "wind";
    case MRD2_CH_SOILT:   return "soilt";
    case MRD2_CH_LEAFWET: return "leafwet";
    default:              return "unknown";
    }
}

uint32_t mrd2_peek_magic(const unsigned char *buf, size_t len)
{
    if (buf == NULL || len < 4)
        return 0u;
    return rd_u32(buf);
}

int mrd2_packet_parse(const unsigned char *buf, size_t len,
                      struct mrd2_packet *out)
{
    int i;
    uint16_t want;

    if (buf == NULL || out == NULL)
        return -1;
    if (len < MRD2_PACKET_BYTES)
        return -1;

    out->magic = rd_u32(buf + MRD2_OFF_MAGIC);
    if (out->magic != MRD2_MAGIC)
        return -2;

    memcpy(out->stnid, buf + MRD2_OFF_STNID, MRD_STNID_LEN);

    out->year = rd_u16(buf + MRD2_OFF_YEAR);
    out->doy  = rd_u16(buf + MRD2_OFF_DOY);

    for (i = 0; i < MRD2_MAX_CHANNELS; i++)
        out->value[i] = rd_i32(buf + MRD2_OFF_VALUES + (i * 4));

    out->version = buf[MRD2_OFF_VERSION];
    out->flags   = buf[MRD2_OFF_FLAGS];
    out->crc     = rd_u16(buf + MRD2_OFF_CRC);

    /* Verify the extended CRC region.  The MRD2 CRC is defined to cover
     * everything ahead of the trailing CRC word -- the channels, the
     * version byte and the flags byte -- i.e. MRD2_CRC_LEN (50) bytes.
     * The channels end at offset 48, so protecting them is just the
     * first 48 bytes. */
    want = mrd_crc16(buf, MRD2_OFF_VERSION);
    if (want != out->crc)
        return -3;

    return 0;
}
