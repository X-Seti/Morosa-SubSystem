/* this belongs in apps/core/video.c - Version: 10 */
/* X-Seti - Nov 21 2026 - Morosa-SubSystem - Native line renderer, copper, chunky-to-planar, blitter area and Paula tick. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

#define FB_WIDTH 832
#define FB_LINES 626
#define LEFT_ABS 0x40
#define MAXPX 2048

static uint32_t to_bgra(uint32_t c, int aga)
{
    if (aga)
        return (c & 255) | (c >> 8 & 255) << 8 | (c >> 16 & 255) << 16 | 0xFF000000u;
    return (c & 15) * 17 | (c >> 4 & 15) * 17 << 8 | (c >> 8 & 15) * 17 << 16 | 0xFF000000u;
}

static int load_colors(PyObject *list, uint32_t *pal, int *npal)
{
    Py_ssize_t n = PySequence_Size(list), i;
    if (n < 0 || n > 256)
        return -1;
    for (i = 0; i < n; i++) {
        PyObject *o = PySequence_GetItem(list, i);
        if (!o)
            return -1;
        pal[i] = (uint32_t)PyLong_AsUnsignedLong(o);
        Py_DECREF(o);
        if (PyErr_Occurred())
            return -1;
    }
    *npal = (int)n;
    return 0;
}

static PyObject *render_line(PyObject *self, PyObject *args)
{
    Py_buffer fbv;
    PyObject *planes, *colors, *sprs, *chgs;
    int ncg = 0, ci = 0, cgx[512], cgi[512];
    uint32_t cgv[512];
    int vpos, x_abs, hs, he, vs, ve, bc0, bc1, bc2, bpu, aga, xorv, off2;
    uint32_t pal[256];
    int npal = 0, i, x;
    Py_buffer pb[8];
    int got = 0;
    int hires, ham, dbl, pf2pri, shres;
    uint32_t *row = NULL;
    int dup = 0;
    static uint8_t pens[MAXPX];
    static uint32_t col[MAXPX * 2];
    static uint8_t pf[MAXPX * 2];
    static int16_t spx[FB_WIDTH];
    int nw = 0, npx, scale, start, win_l, win_r, lo, hi, len;
    int any_spr = 0, clxd = 0, clxcon = 0;
    static uint8_t spm[FB_WIDTH];
    int sprv[8][5];
    uint64_t sda[8], sdb[8];
    int sprw = 16, bc3 = 0, bc4 = 0x11, pver = -1, nrel = 0, havecb = 0;
    Py_buffer cb;
    static PyObject *pal_obj = NULL;
    static int pal_ver = -1, pal_n = 0;
    static uint32_t pal_cache[256];

    if (!PyArg_ParseTuple(args, "w*iOiiiiiiiiiiiiOOOiiiiii", &fbv, &vpos, &planes, &x_abs, &hs, &he, &vs, &ve,
                          &bc0, &bc1, &bc2, &bpu, &aga, &xorv, &off2, &colors, &sprs, &chgs, &dup, &clxcon, &sprw, &bc3, &bc4, &pver))
        return NULL;
    if (vpos < 0 || vpos >= FB_LINES)
        goto done_ok;
    if (pver >= 0 && colors == pal_obj && pver == pal_ver) {
        memcpy(pal, pal_cache, sizeof(pal));
        npal = pal_n;
    } else {
        if (load_colors(colors, pal, &npal) < 0 || npal == 0)
            goto fail;
        if (pver >= 0) {
            memcpy(pal_cache, pal, sizeof(pal));
            pal_obj = colors;
            pal_ver = pver;
            pal_n = npal;
        }
    }
    shres = (bc0 & 0x40) != 0;
    hires = (bc0 & 0x8000) != 0 || shres;
    ham = (bc0 & 0x0800) != 0;
    dbl = (bc0 & 0x0400) != 0;
    pf2pri = (bc2 & 0x40) != 0;
    row = (uint32_t *)((char *)fbv.buf + (size_t)vpos * FB_WIDTH * 4);
    {
        Py_ssize_t nc = PySequence_Size(chgs), k;
        if (nc < 0)
            goto fail;
        for (k = 0; k < nc && ncg < 512; k++) {
            PyObject *t = PySequence_GetItem(chgs, k);
            PyObject *a, *b, *c;
            if (!t)
                goto fail;
            a = PySequence_GetItem(t, 0); b = PySequence_GetItem(t, 1); c = PySequence_GetItem(t, 2);
            if (a && b && c) {
                cgx[ncg] = ((int)PyLong_AsLong(a) - LEFT_ABS) * 2;
                cgi[ncg] = (int)PyLong_AsLong(b) % npal;
                cgv[ncg] = (uint32_t)PyLong_AsUnsignedLong(c);
                ncg++;
            }
            Py_XDECREF(a); Py_XDECREF(b); Py_XDECREF(c); Py_DECREF(t);
            if (PyErr_Occurred())
                goto fail;
        }
    }
    {
        uint32_t bgv = pal[0];
        int j = 0;
        for (x = 0; x < FB_WIDTH; x++) {
            while (j < ncg && cgx[j] <= x) {
                if (cgi[j] == 0)
                    bgv = cgv[j];
                j++;
            }
            row[x] = to_bgra(bgv, aga);
        }
    }
    {
        Py_ssize_t np_;
        if (PyTuple_Check(planes) && PyTuple_GET_SIZE(planes) == 3) {
            PyObject *offs = PyTuple_GET_ITEM(planes, 1);
            long n2 = PyLong_AsLong(PyTuple_GET_ITEM(planes, 2)) * 2;
            Py_ssize_t k;
            if (PyErr_Occurred() || !PyTuple_Check(offs))
                goto fail;
            if (!(vs <= (vpos >> 1) && (vpos >> 1) < ve) || PyTuple_GET_SIZE(offs) == 0 || bpu == 0)
                goto done_ok;
            if (PyObject_GetBuffer(PyTuple_GET_ITEM(planes, 0), &cb, PyBUF_SIMPLE) < 0)
                goto fail;
            havecb = 1;
            for (k = 0; k < PyTuple_GET_SIZE(offs) && k < 8; k++) {
                long o = PyLong_AsLong(PyTuple_GET_ITEM(offs, k));
                if (PyErr_Occurred() || o < 0 || o + n2 > cb.len)
                    goto fail;
                pb[got].buf = (char *)cb.buf + o;
                pb[got].len = n2;
                got++;
            }
            np_ = 0;
        } else {
        np_ = PySequence_Size(planes);
        if (np_ < 0)
            goto fail;
        if (!(vs <= (vpos >> 1) && (vpos >> 1) < ve) || np_ == 0 || bpu == 0)
            goto done_ok;
        if (np_ > 8)
            np_ = 8;
        }
        for (i = 0; i < np_; i++) {
            PyObject *o = PySequence_GetItem(planes, i);
            if (!o)
                goto fail;
            if (PyObject_GetBuffer(o, &pb[got], PyBUF_SIMPLE) < 0) {
                Py_DECREF(o);
                goto fail;
            }
            Py_DECREF(o);
            got++;
            nrel++;
        }
    }
    nw = (int)(pb[0].len / 2);
    if (nw <= 0 || nw * 16 > MAXPX)
        goto done_ok;
    npx = nw * 16;
    {
        int sc1 = bc1 & 15, sc2 = bc1 >> 4 & 15;
        if (aga) {
            sc1 |= (bc1 >> 10 & 3) << 4;
            sc2 |= (bc1 >> 14 & 3) << 4;
        }
        memset(pens, 0, (size_t)npx);
        for (i = 0; i < bpu && i < got; i++) {
            const uint8_t *p = (const uint8_t *)pb[i].buf;
            int w = (int)(pb[i].len / 2);
            int sc = (i & 1 ? sc2 : sc1) * (shres ? 4 : hires ? 2 : 1);
            int m = w < nw ? w : nw;
            if (sc == 0) {
                static uint64_t tbl[256];
                static int tinit = 0;
                int j, nb = m * 2;
                if (!tinit) {
                    for (j = 0; j < 256; j++) {
                        uint64_t v = 0;
                        int k;
                        for (k = 0; k < 8; k++)
                            v |= (uint64_t)(j >> (7 - k) & 1) << (8 * k);
                        tbl[j] = v;
                    }
                    tinit = 1;
                }
                for (j = 0; j < nb; j++) {
                    uint64_t v;
                    memcpy(&v, pens + j * 8, 8);
                    v |= tbl[p[j]] << i;
                    memcpy(pens + j * 8, &v, 8);
                }
                continue;
            }
            for (x = 0; x < m * 16; x++) {
                int sx = x - sc;
                if (sx < 0)
                    continue;
                if (p[(sx >> 4) * 2 + ((sx >> 3) & 1)] >> (7 - (sx & 7)) & 1)
                    pens[x] |= 1 << i;
            }
        }
    }
    if (xorv)
        for (x = 0; x < npx; x++)
            pens[x] ^= (uint8_t)xorv;
    scale = hires ? 1 : 2;
    (void)scale;
    start = (x_abs - LEFT_ABS) * 2;
    /* compose */
    {
        uint32_t prev = pal[0];
        for (x = 0; x < npx; x++) {
            int p = pens[x];
            uint32_t c;
            while (ci < ncg && cgx[ci] <= start + x * scale)
                pal[cgi[ci]] = cgv[ci], ci++;
            int f;
            if (ham && ((!aga && bpu >= 5) || (aga && bpu >= 6))) {
                if (aga) {
                    int ctl, d, idx;
                    if (bpu == 8) {
                        ctl = p >> 6 & 3; d = (p & 63) << 2; idx = p & 63;
                    } else {
                        ctl = p >> 4 & 3; d = (p & 15) * 17; idx = p & 15;
                    }
                    if (ctl == 0)
                        prev = pal[idx % npal];
                    else {
                        uint32_t r = prev >> 16 & 255, g = prev >> 8 & 255, b = prev & 255;
                        if (ctl == 1) b = d; else if (ctl == 2) r = d; else g = d;
                        prev = r << 16 | g << 8 | b;
                    }
                } else {
                    int ctl = p >> 4 & 3, d = p & 15;
                    if (ctl == 0)
                        prev = pal[d % npal];
                    else {
                        uint32_t r = prev >> 8 & 15, g = prev >> 4 & 15, b = prev & 15;
                        if (ctl == 1) b = d; else if (ctl == 2) r = d; else g = d;
                        prev = r << 8 | g << 4 | b;
                    }
                }
                c = prev; f = 1;
            } else if (dbl) {
                int p1, p2, a, b;
                uint32_t ca, cb;
                int fa, fb2;
                if (aga) {
                    p1 = (p & 1) | (p >> 2 & 1) << 1 | (p >> 4 & 1) << 2 | (p >> 6 & 1) << 3;
                    p2 = (p >> 1 & 1) | (p >> 3 & 1) << 1 | (p >> 5 & 1) << 2 | (p >> 7 & 1) << 3;
                    ca = pal[p1 % npal];
                    cb = pal[((off2 + p2) & 255) % npal];
                } else {
                    p1 = (p & 1) | (p >> 2 & 1) << 1 | (p >> 4 & 1) << 2;
                    p2 = (p >> 1 & 1) | (p >> 3 & 1) << 1 | (p >> 5 & 1) << 2;
                    ca = pal[p1 % npal]; cb = pal[(8 + p2) % npal];
                }
                /* ca = playfield 1 colour, cb = playfield 2 colour */
                if (pf2pri) { a = p2; b = p1; fa = 2; fb2 = 1; c = 0; {
                        uint32_t t = ca; ca = cb; cb = t; } }
                else { a = p1; b = p2; fa = 1; fb2 = 2; }
                if (a != 0) { c = ca; f = fa; }
                else if (b != 0) { c = cb; f = fb2; }
                else { c = pal[0]; f = 0; }
            } else if (bpu == 6) {
                c = pal[(p & 31) % npal];
                if (p & 32)
                    c = aga ? (c >> 1 & 0x7F7F7F) : (c >> 1 & 0x777);
                f = p != 0;
            } else {
                c = pal[p % npal];
                f = p != 0;
            }
            if (hires) {
                col[x] = c; pf[x] = (uint8_t)f;
            } else {
                col[2 * x] = col[2 * x + 1] = c;
                pf[2 * x] = pf[2 * x + 1] = (uint8_t)f;
            }
        }
    }
    if (shres) {
        for (x = 0; x < npx / 2; x++) {
            col[x] = col[2 * x];
            pf[x] = pf[2 * x];
        }
        npx /= 2;
    }
    len = npx * scale;
    while (ci < ncg)
        pal[cgi[ci]] = cgv[ci], ci++;
    win_l = (hs - LEFT_ABS) * 2;
    win_r = (he - LEFT_ABS) * 2;
    lo = win_l > 0 ? win_l : 0;
    if (start > lo) lo = start;
    hi = win_r < FB_WIDTH ? win_r : FB_WIDTH;
    if (start + len < hi) hi = start + len;
    if (hi <= lo)
        goto done_ok;
    /* sprites */
    for (i = 0; i < 8; i++) {
        PyObject *t = PySequence_GetItem(sprs, i);
        PyObject *o;
        int k;
        if (!t)
            goto fail;
        for (k = 0; k < 5; k++) {
            o = PySequence_GetItem(t, k);
            if (!o) { Py_DECREF(t); goto fail; }
            if (k >= 3) {
                uint64_t u = PyLong_AsUnsignedLongLongMask(o);
                if (k == 3) sda[i] = u; else sdb[i] = u;
            }
            if (k < 3)
                sprv[i][k] = (int)PyLong_AsLong(o);
            else
                sprv[i][k] = 0;
            Py_DECREF(o);
        }
        Py_DECREF(t);
        if (sprv[i][0])
            any_spr = 1;
    }
    if (any_spr) {
        int n, have = 0;
        for (x = 0; x < FB_WIDTH; x++)
            spx[x] = -1, spm[x] = 0;
        for (n = 7; n >= 0; n--) {
            int *s = sprv[n];
            int hp, x35, pw, base, attached, k;
            uint64_t a = sda[n], b = sdb[n];
            if (!s[0])
                continue;
            hp = (s[1] & 0xFF) << 3 | (s[2] & 1) << 2;
            if (aga)
                hp |= (s[2] >> 4 & 1) << 1 | (s[2] >> 3 & 1);
            x35 = hp - LEFT_ABS * 4;
            pw = 4;
            if (aga) {
                int sr = bc3 >> 6 & 3;
                pw = sr == 0 ? (shres ? 2 : 4) : sr == 1 ? 4 : sr == 2 ? 2 : 1;
            }
            base = (aga ? (n & 1 ? bc4 & 15 : bc4 >> 4 & 15) << 4 : 16) + 4 * (n >> 1);
            attached = (n & 1) && (s[2] & 0x80);
            for (i = 0; i < sprw; i++) {
                int sh = sprw - 1 - i;
                int v = (int)(a >> sh & 1) | (int)(b >> sh & 1) << 1;
                int xa, xb;
                if (!v)
                    continue;
                xa = (x35 + i * pw) >> 1;
                xb = (x35 + (i + 1) * pw + 1) >> 1;
                if (xb <= xa)
                    xb = xa + 1;
                for (k = xa; k < xb; k++) {
                    int xx = k;
                    if (xx >= 0 && xx < FB_WIDTH) {
                        if (!(n & 1) || (clxcon >> (12 + (n >> 1)) & 1))
                            spm[xx] |= (uint8_t)(1 << (n >> 1));
                        if (attached) {
                            int ov = (int)(sda[n - 1] >> sh & 1) | (int)(sdb[n - 1] >> sh & 1) << 1;
                            spx[xx] = (int16_t)((n >> 1) << 8 | ((aga ? (bc4 & 15) << 4 : 16) + (ov | v << 2)));
                        } else
                            spx[xx] = (int16_t)((n >> 1) << 8 | (base + v));
                        have = 1;
                    }
                }
            }
        }
        if (have) {
            int pf1p = bc2 & 7, pf2p = bc2 >> 3 & 7;
            for (x = lo; x < hi; x++) {
                int sp = spx[x];
                if (sp >= 0) {
                    int grp = sp >> 8, idx = sp & 255;
                    int f = pf[x - start];
                    if (f == 0 || grp < (f == 2 ? pf2p : pf1p))
                        col[x - start] = pal[idx % npal];
                }
            }
        }
    }
    {
        int en = clxcon & 63, mv = clxcon >> 6 & 63;
        int e1 = en & 0x15, e2 = en & 0x2A;
        for (x = lo; x < hi; x++) {
            int pp = pens[(x - start) * (shres ? 2 : 1) / scale];
            int h1 = !((pp ^ mv) & e1), h2 = !((pp ^ mv) & e2);
            int m = any_spr ? spm[x] : 0, k;
            if (h1 && h2)
                clxd |= 1;
            for (k = 0; k < 4; k++) {
                if (m >> k & 1) {
                    if (h1) clxd |= 2 << k;
                    if (h2) clxd |= 32 << k;
                }
            }
            if (m & 3 && m & 12) clxd |= 1 << 9;
            if (m & 3 && m & 48) clxd |= 1 << 10;
            if (m & 3 && m & 192) clxd |= 1 << 11;
            if (m & 12 && m & 48) clxd |= 1 << 12;
            if (m & 12 && m & 192) clxd |= 1 << 13;
            if (m & 48 && m & 192) clxd |= 1 << 14;
        }
    }
    for (x = lo; x < hi; x++)
        row[x] = to_bgra(col[x - start], aga);
done_ok:
    if (dup && row && vpos + 1 < FB_LINES)
        memcpy(row + FB_WIDTH, row, FB_WIDTH * 4);
    for (i = 0; i < nrel; i++)
        PyBuffer_Release(&pb[i]);
    if (havecb)
        PyBuffer_Release(&cb);
    PyBuffer_Release(&fbv);
    return PyLong_FromLong(clxd);
fail:
    for (i = 0; i < nrel; i++)
        PyBuffer_Release(&pb[i]);
    if (havecb)
        PyBuffer_Release(&cb);
    PyBuffer_Release(&fbv);
    return NULL;
}


/* Run one line of copper slots; returns the new state tuple. */
static int cop_cond(int v, int h, int *w, PyObject *bcb) {
    int vp = w[0], hp = w[1], vm = w[2], hm = w[3], bfd = w[4];
    if (!bfd) {
        PyObject *r = PyObject_CallNoArgs(bcb);
        int busy = r ? PyObject_IsTrue(r) : -1;
        Py_XDECREF(r);
        if (busy) return busy < 0 ? -1 : 0;
    }
    int vv = v & vm, hh = h & hm;
    return vv > (vp & vm) || (vv == (vp & vm) && hh >= (hp & hm));
}

static PyObject *copper_run(PyObject *self, PyObject *args) {
    Py_buffer chip;
    unsigned mask;
    int pc, lc1, lc2, cc, waiting, halted, skip, w[5], v, ccl;
    PyObject *wcb, *bcb;
    if (!PyArg_ParseTuple(args, "w*IiiiiiiiiiiiiiiOO", &chip, &mask, &pc, &lc1, &lc2, &cc, &waiting, &halted, &skip,
                          &w[0], &w[1], &w[2], &w[3], &w[4], &v, &ccl, &wcb, &bcb))
        return NULL;
    uint8_t *m = chip.buf;
    for (int h = 0; h < ccl && !halted; h += 2) {
        if (waiting) {
            int c = cop_cond(v, h, w, bcb);
            if (c < 0) { PyBuffer_Release(&chip); return NULL; }
            if (!c) continue;
            waiting = 0;
        }
        unsigned a1 = (unsigned)pc & mask & ~1u, a2 = ((unsigned)pc + 2) & mask & ~1u;
        int w1 = m[a1] << 8 | m[a1 + 1], w2 = m[a2] << 8 | m[a2 + 1];
        pc += 4;
        if (skip) { skip = 0; continue; }
        if (!(w1 & 1)) {
            int reg = w1 & 0x1FE;
            if (reg < ((cc & 2) ? 0x40 : 0x80)) { halted = 1; continue; }
            if (reg == 0x2E) cc = w2;
            else if (reg == 0x80) lc1 = (lc1 & 0xFFFF) | (w2 & 0x1F) << 16;
            else if (reg == 0x82) lc1 = (lc1 & 0x1F0000) | (w2 & 0xFFFE);
            else if (reg == 0x84) lc2 = (lc2 & 0xFFFF) | (w2 & 0x1F) << 16;
            else if (reg == 0x86) lc2 = (lc2 & 0x1F0000) | (w2 & 0xFFFE);
            else if (reg == 0x88 || reg == 0x8A) { pc = reg == 0x88 ? lc1 : lc2; waiting = halted = skip = 0; }
            else {
                PyObject *r = PyObject_CallFunction(wcb, "iii", reg, w2, h);
                int dma = r ? PyObject_IsTrue(r) : -1;
                Py_XDECREF(r);
                if (dma < 0) { PyBuffer_Release(&chip); return NULL; }
                if (!dma) break;
            }
            continue;
        }
        w[0] = w1 >> 8 & 0xFF; w[1] = w1 & 0xFE; w[2] = (w2 >> 8 & 0x7F) | 0x80; w[3] = w2 & 0xFE; w[4] = (w2 & 0x8000) != 0;
        if (w2 & 1) {
            int c = cop_cond(v, h, w, bcb);
            if (c < 0) { PyBuffer_Release(&chip); return NULL; }
            if (c) skip = 1;
        } else waiting = 1;
    }
    PyBuffer_Release(&chip);
    return Py_BuildValue("(iiiiiiiiiiii)", pc, lc1, lc2, cc, waiting, halted, skip, w[0], w[1], w[2], w[3], w[4]);
}

/* Akiko chunky to planar: 8 longwords in, 8 out. */
static PyObject *c2p(PyObject *self, PyObject *args) {
    PyObject *seq;
    if (!PyArg_ParseTuple(args, "O", &seq)) return NULL;
    uint32_t b[8], r[8] = {0};
    for (int i = 0; i < 8; i++) {
        PyObject *o = PySequence_GetItem(seq, i);
        if (!o) return NULL;
        b[i] = (uint32_t)PyLong_AsUnsignedLongMask(o);
        Py_DECREF(o);
    }
    for (int i = 0; i < 256; i++)
        if (b[7 - (i >> 5)] >> (i & 31) & 1) r[i & 7] |= 1u << (i >> 3);
    return Py_BuildValue("(IIIIIIII)", r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]);
}


/* ---- blitter area mode ---- */
static inline uint32_t rd16(const uint8_t *chip, long long mask, long long a)
{
    a &= mask & ~1LL;
    return (uint32_t)chip[a] << 8 | chip[a + 1];
}

static inline void wr16(uint8_t *chip, long long mask, long long a, uint32_t v)
{
    a &= mask & ~1LL;
    chip[a] = (uint8_t)(v >> 8);
    chip[a + 1] = (uint8_t)v;
}

static uint32_t minterm(uint32_t lf, uint32_t a, uint32_t b, uint32_t c)
{
    uint32_t out = 0;
    int i;
    for (i = 0; i < 8; i++)
        if (lf >> i & 1)
            out |= ((i & 4) ? a : ~a) & ((i & 2) ? b : ~b) & ((i & 1) ? c : ~c);
    return out & 0xFFFF;
}

static PyObject *blit_area(PyObject *self, PyObject *args)
{
    Py_buffer chip;
    long long mask, con0, con1, afwm, alwm, adat, bdat, cdat, apt, bpt, cpt, dpt, amod, bmod, cmod, dmod, width, height;
    long long zero = 1, y, w;
    int i;
    if (!PyArg_ParseTuple(args, "w*LLLLLLLLLLLLLLLLLL", &chip, &mask, &con0, &con1, &afwm, &alwm, &adat, &bdat, &cdat, &apt, &bpt, &cpt, &dpt,
                          &amod, &bmod, &cmod, &dmod, &width, &height))
        return NULL;
    {
        uint8_t *ram = (uint8_t *)chip.buf;
        int use_a = con0 >> 11 & 1, use_b = con0 >> 10 & 1, use_c = con0 >> 9 & 1, use_d = con0 >> 8 & 1;
        int ash = (int)(con0 >> 12 & 15), bsh = (int)(con1 >> 12 & 15), desc = (con1 & 2) != 0;
        int fill_ex = (con1 & 0x10) != 0, fill_in = (con1 & 0x08) != 0;
        uint32_t lf = (uint32_t)(con0 & 0xFF);
        long long step = desc ? -2 : 2;
        for (y = 0; y < height; y++) {
            uint32_t fci = (uint32_t)(con1 >> 2 & 1), a_prev = 0, b_prev = 0;
            for (w = 0; w < width; w++) {
                uint32_t a, ah, bh, d;
                if (use_a) { adat = rd16(ram, mask, apt); apt += step; }
                if (use_b) { bdat = rd16(ram, mask, bpt); bpt += step; }
                if (use_c) { cdat = rd16(ram, mask, cpt); cpt += step; }
                a = (uint32_t)adat;
                if (w == 0) a &= (uint32_t)afwm;
                if (w == width - 1) a &= (uint32_t)alwm;
                if (desc) {
                    ah = (uint32_t)((((uint64_t)a << 16 | a_prev) << ash >> 16) & 0xFFFF);
                    bh = (uint32_t)((((uint64_t)bdat << 16 | b_prev) << bsh >> 16) & 0xFFFF);
                } else {
                    ah = (uint32_t)((((uint64_t)a_prev << 16 | a) >> ash) & 0xFFFF);
                    bh = (uint32_t)((((uint64_t)b_prev << 16 | (uint32_t)bdat) >> bsh) & 0xFFFF);
                }
                a_prev = a;
                b_prev = (uint32_t)bdat;
                d = minterm(lf, ah, bh, (uint32_t)cdat);
                if (fill_ex || fill_in) {
                    uint32_t out = 0, fc = fci;
                    for (i = 0; i < 16; i++) {
                        uint32_t bit = d >> i & 1;
                        out |= (fill_in ? (bit | fc) : (bit ^ fc)) << i;
                        fc ^= bit;
                    }
                    fci = fc;
                    d = out;
                }
                if (d) zero = 0;
                if (use_d) { wr16(ram, mask, dpt, d); dpt += step; }
            }
            if (use_a) apt += desc ? -amod : amod;
            if (use_b) bpt += desc ? -bmod : bmod;
            if (use_c) cpt += desc ? -cmod : cmod;
            if (use_d) dpt += desc ? -dmod : dmod;
        }
    }
    PyBuffer_Release(&chip);
    return Py_BuildValue("(LLLLLLLL)", apt, bpt, cpt, dpt, adat, bdat, cdat, zero);
}


/* ---- Paula audio tick ----
   channel state list: 0 on, 1 per, 2 counter, 3 ptr, 4 left bytes, 5 word, 6 byte_no, 7 out (16 bit scale),
   8 vol, 9 lc, 10 len words, 11 format (0 8-bit, 1 16, 2 24, 3 32) */
typedef struct { long long v[12]; } Chan;

static PyObject *paula_tick(PyObject *self, PyObject *args)
{
    Py_buffer chip;
    PyObject *states, *samples;
    long long mask, clocks, maxs;
    double due, per_sample;
    int gshift, n, i;
    long long irq = 0;
    Chan ch[16];
    if (!PyArg_ParseTuple(args, "w*LOLddOLi", &chip, &mask, &states, &clocks, &due, &per_sample, &samples, &maxs, &gshift))
        return NULL;
    n = (int)PyList_Size(states);
    if (n > 16) n = 16;
    for (i = 0; i < n; i++) {
        PyObject *st = PyList_GetItem(states, i);
        int k;
        for (k = 0; k < 12; k++)
            ch[i].v[k] = PyLong_AsLongLong(PyList_GetItem(st, k));
    }
    {
        const uint8_t *ram = (const uint8_t *)chip.buf;
        while (clocks > 0) {
            long long t = (long long)due;
            if (t < 1) t = 1;
            if (t > clocks) t = clocks;
            for (i = 0; i < n; i++) {
                Chan *c = &ch[i];
                long long per;
                if (!c->v[0]) continue;
                per = c->v[1] ? c->v[1] : 0x10000;
                c->v[2] += t;
                while (c->v[2] >= per) {
                    c->v[2] -= per;
                    switch (c->v[11]) {
                    case 0: {
                        long long b;
                        if (c->v[6] >= 2) {
                            c->v[5] = rd16(ram, mask, c->v[3]);
                            c->v[3] = (c->v[3] + 2) & 0xFFFFFFFFLL;
                            c->v[4] -= 2;
                            c->v[6] = 0;
                            if (c->v[4] <= 0) {
                                c->v[3] = c->v[9];
                                c->v[4] = c->v[10] ? c->v[10] * 2 : 0x20000;
                                if (i < 4) irq |= 1LL << (7 + i);
                            }
                        }
                        b = c->v[5] >> (8 - 8 * c->v[6]) & 0xFF;
                        c->v[7] = (long long)(int8_t)b * 256;
                        c->v[6]++;
                        break; }
                    default: {
                        int nb = (int)c->v[11] + 1;
                        long long a = c->v[3] & mask, val = 0;
                        int k;
                        for (k = 0; k < nb; k++)
                            val = val << 8 | ram[(a + k) & mask];
                        if (nb == 2) c->v[7] = (int16_t)val;
                        else if (nb == 3) c->v[7] = ((val & 0x800000) ? (val - 0x1000000) : val) >> 8;
                        else c->v[7] = (int32_t)val >> 16;
                        c->v[3] = (c->v[3] + nb) & 0xFFFFFFFFLL;
                        c->v[4] -= nb;
                        if (c->v[4] <= 0) {
                            c->v[3] = c->v[9];
                            c->v[4] = c->v[10] ? c->v[10] * 2 : 0x20000;
                            if (i < 4) irq |= 1LL << (7 + i);
                        }
                        break; }
                    }
                }
            }
            clocks -= t;
            due -= (double)t;
            if (due < 1) {
                long long l = 0, r = 0;
                due += per_sample;
                for (i = 0; i < n; i++) {
                    long long m = (ch[i].v[7] * ch[i].v[8]) >> 8;
                    if ((i & 3) == 0 || (i & 3) == 3) l += m; else r += m;
                }
                if (PyList_GET_SIZE(samples) < maxs) {
                    PyObject *tup = Py_BuildValue("(LL)", l >> gshift, r >> gshift);
                    if (!tup) { PyBuffer_Release(&chip); return NULL; }
                    PyList_Append(samples, tup);
                    Py_DECREF(tup);
                }
            }
        }
    }
    for (i = 0; i < n; i++) {
        PyObject *st = PyList_GetItem(states, i);
        int k;
        for (k = 0; k < 12; k++) {
            PyObject *o = PyLong_FromLongLong(ch[i].v[k]);
            PyList_SetItem(st, k, o);
        }
    }
    PyBuffer_Release(&chip);
    return Py_BuildValue("(dL)", due, irq);
}

static PyMethodDef methods[] = {
    {"paula_tick", paula_tick, METH_VARARGS, "paula_tick(chip, mask, states, clocks, due, per_sample, samples, maxs, gshift)"},
    {"blit_area", blit_area, METH_VARARGS, "blit_area(chip, mask, ...) runs a blitter area operation"},
    {"render_line", render_line, METH_VARARGS, "render_line(fb, row, planes, ..., dup) draws one raster row"},
    {"copper_run", copper_run, METH_VARARGS, "copper_run(...) runs one line of copper slots"},
    {"c2p", c2p, METH_VARARGS, "c2p(buf) chunky to planar"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef mod = {PyModuleDef_HEAD_INIT, "video_ext", NULL, -1, methods};

PyMODINIT_FUNC PyInit_video_ext(void) { return PyModule_Create(&mod); }
