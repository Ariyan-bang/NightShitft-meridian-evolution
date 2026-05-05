/* mrd_framedump.c - a debugging aid that dumps telemetry frames.
 *
 * Reads a frame file (a spool, or a single captured frame) and prints
 * each frame's fields in a human-readable block on stdout.  Unlike
 * mrd_ingest it writes nothing to the store and runs no QC gate; it
 * exists so a field tech can see exactly what bytes a logger put on the
 * wire -- the magic, the station id, the raw and scaled channels, the
 * flags, and both the stored CRC and the CRC recomputed over the frame,
 * so a mismatch is obvious at a glance.
 *
 * It understands both frame formats.  The leading big-endian magic
 * tells it which: MRD1 frames are 44 bytes and decode with packet.c,
 * MRD2 frames are 52 bytes and decode with packet2.c.  A mixed file is
 * fine; each frame is sized and decoded on its own magic.  Anything
 * whose magic is neither is reported and halts the walk, because once
 * the reader has lost frame alignment it cannot trust the rest.
 *
 * 2026-03.  Added as a standalone target; it touches no existing tool.
 */
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "packet.h"
#include "packet2.h"
#include "decode.h"
#include "decode2.h"

/* Largest frame we might read in one go. */
#define FD_MAXFRAME MRD2_PACKET_BYTES

static void usage(const char *argv0)
{
    fprintf(stderr,
        "usage: %s <framefile> [--limit N]\n"
        "  Dump MRD1/MRD2 telemetry frames as human-readable blocks.\n"
        "  --limit N   stop after N frames (0 = no limit, the default)\n",
        argv0);
}

/* Render a 4-byte magic as its ASCII spelling into dst (>= 5 bytes),
 * substituting '.' for non-printable bytes. */
static void magic_ascii(uint32_t magic, char *dst)
{
    int i;
    for (i = 0; i < 4; i++) {
        unsigned char c = (unsigned char)((magic >> (24 - 8 * i)) & 0xFFu);
        dst[i] = (c >= 0x20 && c < 0x7F) ? (char)c : '.';
    }
    dst[4] = '\0';
}

static void dump_mrd1(const unsigned char *buf, long idx, FILE *out)
{
    struct mrd_packet pkt;
    struct mrd_decoded dec;
    char mags[5];
    char line[256];
    uint16_t stored, recomputed;
    int rc, i;

    stored = (uint16_t)((buf[42] << 8) | buf[43]);
    recomputed = mrd_crc16(buf, 42);

    rc = mrd_packet_parse(buf, MRD_PACKET_BYTES, &pkt);
    magic_ascii(MRD_MAGIC, mags);

    fprintf(out, "frame %ld: MRD1 (%d bytes) magic=0x%08X \"%s\"\n",
            idx, MRD_PACKET_BYTES, MRD_MAGIC, mags);
    fprintf(out, "  crc: stored=0x%04X recomputed=0x%04X %s\n",
            stored, recomputed,
            stored == recomputed ? "OK" : "MISMATCH");

    if (rc != 0) {
        fprintf(out, "  parse: FAILED rc=%d (%s)\n", rc,
                rc == -2 ? "bad magic" :
                rc == -3 ? "crc mismatch" : "short/null");
        return;
    }

    mrd_decode(&pkt, &dec);
    fprintf(out, "  stnid=\"%s\" year=%d doy=%d flags=0x%04X%s%s\n",
            dec.stnid, dec.year, dec.doy, dec.flags,
            dec.suspect ? " suspect" : "",
            dec.manual  ? " manual"  : "");
    fprintf(out, "  channels (raw x100 -> scaled):\n");
    for (i = 0; i < MRD_MAX_CHANNELS; i++)
        fprintf(out, "      %-7s %10d -> %10.2f\n",
                mrd_channel_name(i), pkt.value[i], dec.ch[i]);

    if (mrd_decoded_format(&dec, line, sizeof(line)) > 0)
        fprintf(out, "  %s\n", line);
}

static void dump_mrd2(const unsigned char *buf, long idx, FILE *out)
{
    struct mrd2_packet pkt;
    struct mrd2_decoded dec;
    char mags[5];
    char line[256];
    uint16_t stored, recomputed;
    int rc, i;

    stored = (uint16_t)((buf[MRD2_OFF_CRC] << 8) | buf[MRD2_OFF_CRC + 1]);
    /* Recompute over the full extended region the format defines, so a
     * tech sees the honest checksum regardless of how any one decoder
     * chooses to verify it. */
    recomputed = mrd_crc16(buf, MRD2_CRC_LEN);

    rc = mrd2_packet_parse(buf, MRD2_PACKET_BYTES, &pkt);
    magic_ascii(MRD2_MAGIC, mags);

    fprintf(out, "frame %ld: MRD2 (%d bytes) magic=0x%08X \"%s\"\n",
            idx, MRD2_PACKET_BYTES, MRD2_MAGIC, mags);
    fprintf(out, "  crc: stored=0x%04X recomputed=0x%04X %s\n",
            stored, recomputed,
            stored == recomputed ? "OK" : "MISMATCH");

    if (rc != 0) {
        fprintf(out, "  parse: FAILED rc=%d (%s)\n", rc,
                rc == -2 ? "bad magic" :
                rc == -3 ? "crc mismatch" : "short/null");
        return;
    }

    mrd2_decode(&pkt, &dec);
    fprintf(out, "  stnid=\"%s\" year=%d doy=%d version=%d "
                 "flags=0x%02X%s%s\n",
            dec.stnid, dec.year, dec.doy, dec.version, dec.flags,
            dec.suspect ? " suspect" : "",
            dec.manual  ? " manual"  : "");
    fprintf(out, "  channels (raw x100 -> scaled):\n");
    for (i = 0; i < MRD2_MAX_CHANNELS; i++)
        fprintf(out, "      %-7s %10d -> %10.2f\n",
                mrd2_channel_name(i), pkt.value[i], dec.ch[i]);

    if (mrd2_decoded_format(&dec, line, sizeof(line)) > 0)
        fprintf(out, "  %s\n", line);
}

/* Read exactly n more bytes into buf+have.  Returns the number of extra
 * bytes actually read. */
static size_t read_rest(FILE *fp, unsigned char *buf, size_t have, size_t n)
{
    return fread(buf + have, 1, n, fp);
}

int main(int argc, char **argv)
{
    const char *path;
    FILE *fp;
    unsigned char buf[FD_MAXFRAME];
    long limit = 0;
    long idx = 0;
    long mrd1 = 0, mrd2 = 0;

    if (argc < 2 || argc > 4) {
        usage(argv[0]);
        return 1;
    }
    path = argv[1];

    if (argc >= 3) {
        if (strcmp(argv[2], "--limit") == 0 && argc == 4) {
            limit = atol(argv[3]);
        } else {
            usage(argv[0]);
            return 1;
        }
    }

    fp = fopen(path, "rb");
    if (fp == NULL) {
        fprintf(stderr, "mrd_framedump: cannot open %s\n", path);
        return 1;
    }

    for (;;) {
        size_t head, want, rest;
        uint32_t magic;

        if (limit > 0 && idx >= limit)
            break;

        /* Peek the 4-byte magic to size the frame. */
        head = fread(buf, 1, 4, fp);
        if (head == 0)
            break;                      /* clean end of file */
        if (head < 4) {
            fprintf(stderr,
                "mrd_framedump: short tail of %zu byte(s) at end\n", head);
            break;
        }

        magic = mrd2_peek_magic(buf, 4);
        if (magic == MRD_MAGIC)
            want = MRD_PACKET_BYTES;
        else if (magic == MRD2_MAGIC)
            want = MRD2_PACKET_BYTES;
        else {
            char mags[5];
            magic_ascii(magic, mags);
            fprintf(stderr,
                "mrd_framedump: frame %ld has unknown magic 0x%08X \"%s\";"
                " stopping (lost alignment)\n", idx, magic, mags);
            break;
        }

        rest = read_rest(fp, buf, 4, want - 4);
        if (rest < want - 4) {
            fprintf(stderr,
                "mrd_framedump: short frame %ld: have %zu of %zu bytes\n",
                idx, 4 + rest, want);
            break;
        }

        if (want == MRD_PACKET_BYTES) {
            dump_mrd1(buf, idx, stdout);
            mrd1++;
        } else {
            dump_mrd2(buf, idx, stdout);
            mrd2++;
        }
        idx++;
    }

    fclose(fp);

    fprintf(stderr, "mrd_framedump: %ld frame(s) dumped (MRD1=%ld MRD2=%ld)\n",
            idx, mrd1, mrd2);
    return 0;
}
