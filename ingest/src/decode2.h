/* decode2.h - higher level decode helpers for MRD2 frames.
 *
 * Mirrors decode.h for the eight-channel MRD2 frame.  As with the MRD1
 * decode layer, this sits strictly on top of packet2.c: it turns a
 * parsed struct mrd2_packet into a clean station id, year/doy, and the
 * eight channels already in engineering units, so no caller downstream
 * repeats the scaling or the id trim.
 *
 * The first six channels line up one-for-one with the MRD1 decode, so a
 * caller that only cares about the classic six can read ch[0..5] of an
 * mrd2_decoded exactly as it would an mrd_decoded.  The two new agronomy
 * channels follow at ch[6] (soil temperature) and ch[7] (leaf wetness).
 *
 * 2026-03.  Does not re-read the wire format; all it knows is packet2.h.
 */
#ifndef MERIDIAN_DECODE2_H
#define MERIDIAN_DECODE2_H

#include <stddef.h>
#include "packet2.h"

/* An MRD2 frame after decode: identity plus channels in engineering
 * units.  The channel array is indexed by enum mrd2_channel. */
struct mrd2_decoded {
    char   stnid[MRD_STNID_LEN + 1]; /* trimmed, NUL terminated      */
    int    year;
    int    doy;
    int    version;                  /* frame format version byte    */
    double ch[MRD2_MAX_CHANNELS];
    unsigned flags;
    int    suspect;                  /* nonzero if SUSPECT flag set   */
    int    manual;                   /* nonzero if MANUAL flag set    */
};

/* Trim the frame's space-padded station id into dst (>= MRD_STNID_LEN+1
 * bytes) and return the trimmed length.  Same by-hand right trim as the
 * MRD1 path (MRD-227) so both formats agree on a station's name. */
int mrd2_decode_stnid(const char raw[MRD_STNID_LEN], char *dst);

/* Fill out from an already-parsed packet.  Returns 0, or -1 if a
 * pointer is NULL. */
int mrd2_decode(const struct mrd2_packet *p, struct mrd2_decoded *out);

/* Named channel accessors, for readability at the call sites. */
double mrd2_decoded_tmax(const struct mrd2_decoded *d);
double mrd2_decoded_tmin(const struct mrd2_decoded *d);
double mrd2_decoded_rain(const struct mrd2_decoded *d);
double mrd2_decoded_srad(const struct mrd2_decoded *d);
double mrd2_decoded_rh(const struct mrd2_decoded *d);
double mrd2_decoded_wind(const struct mrd2_decoded *d);
double mrd2_decoded_soilt(const struct mrd2_decoded *d);
double mrd2_decoded_leafwet(const struct mrd2_decoded *d);

/* Same plausibility gate as the MRD1 decode: a wide year window and a
 * 1..366 doy.  The model layer owns the real calendar. */
int mrd2_decoded_date_ok(const struct mrd2_decoded *d);

/* Format a decoded reading as one human line into buf (size n),
 * snprintf style (returns the number of bytes that would be written). */
int mrd2_decoded_format(const struct mrd2_decoded *d, char *buf, size_t n);

#endif
