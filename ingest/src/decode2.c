/* decode2.c - higher level decode helpers for MRD2 frames.
 *
 * 2026-03.  Companion to decode.c.  Everything it knows about the wire
 * frame comes from packet2.h; the scaling is the shared mrd_scale from
 * packet.c, so the two new channels are converted the same way as the
 * classic six and there is no second copy of "/ 100.0" to drift.
 */
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <string.h>
#include "decode2.h"

int mrd2_decode_stnid(const char raw[MRD_STNID_LEN], char *dst)
{
    int i;
    int len;

    if (raw == NULL || dst == NULL)
        return 0;

    /* Fixed-width, not NUL terminated on the wire; copy and terminate. */
    memcpy(dst, raw, MRD_STNID_LEN);
    dst[MRD_STNID_LEN] = '\0';

    /* Right-trim spaces, mirroring the MRD1 path on purpose (MRD-227).
     * Leading spaces are left as-is: no station id begins with one, so
     * a leading space more likely marks corruption worth keeping
     * visible. */
    for (i = MRD_STNID_LEN - 1; i >= 0; i--) {
        if (dst[i] == ' ')
            dst[i] = '\0';
        else
            break;
    }

    len = 0;
    while (dst[len] != '\0')
        len++;
    return len;
}

int mrd2_decode(const struct mrd2_packet *p, struct mrd2_decoded *out)
{
    int i;

    if (p == NULL || out == NULL)
        return -1;

    memset(out, 0, sizeof(*out));

    mrd2_decode_stnid(p->stnid, out->stnid);

    out->year    = (int)p->year;
    out->doy     = (int)p->doy;
    out->version = (int)p->version;

    for (i = 0; i < MRD2_MAX_CHANNELS; i++)
        out->ch[i] = mrd_scale(p->value[i]);

    out->flags   = (unsigned)p->flags;
    out->suspect = (p->flags & MRD2_FLAG_SUSPECT) ? 1 : 0;
    out->manual  = (p->flags & MRD2_FLAG_MANUAL) ? 1 : 0;

    return 0;
}

double mrd2_decoded_tmax(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_TMAX] : 0.0;
}

double mrd2_decoded_tmin(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_TMIN] : 0.0;
}

double mrd2_decoded_rain(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_RAIN] : 0.0;
}

double mrd2_decoded_srad(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_SRAD] : 0.0;
}

double mrd2_decoded_rh(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_RH] : 0.0;
}

double mrd2_decoded_wind(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_WIND] : 0.0;
}

double mrd2_decoded_soilt(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_SOILT] : 0.0;
}

double mrd2_decoded_leafwet(const struct mrd2_decoded *d)
{
    return d ? d->ch[MRD2_CH_LEAFWET] : 0.0;
}

int mrd2_decoded_date_ok(const struct mrd2_decoded *d)
{
    if (d == NULL)
        return 0;
    if (d->year < 2000 || d->year > 2100)
        return 0;
    if (d->doy < 1 || d->doy > 366)
        return 0;
    return 1;
}

int mrd2_decoded_format(const struct mrd2_decoded *d, char *buf, size_t n)
{
    if (d == NULL || buf == NULL || n == 0)
        return 0;

    return snprintf(buf, n,
        "%-8s %4d/%03d tmax=%.2f tmin=%.2f rain=%.2f srad=%.2f "
        "rh=%.2f wind=%.2f soilt=%.2f leafwet=%.2f flags=0x%02x v%d",
        d->stnid, d->year, d->doy,
        d->ch[MRD2_CH_TMAX], d->ch[MRD2_CH_TMIN], d->ch[MRD2_CH_RAIN],
        d->ch[MRD2_CH_SRAD], d->ch[MRD2_CH_RH], d->ch[MRD2_CH_WIND],
        d->ch[MRD2_CH_SOILT], d->ch[MRD2_CH_LEAFWET],
        d->flags, d->version);
}
