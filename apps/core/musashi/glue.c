/* this belongs in apps/core/musashi/glue.c - Version: 5 */
/* X-Seti - Nov 21 2026 - Morosa-SubSystem - Python binding for the Musashi 68k core. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include "m68k.h"
extern int m68k_fpu_mode;

int cpu_log_enabled = 0;
int m68k_is_stopped(void);

typedef struct {
    PyObject_HEAD
    void *ctx;
    int type;
    uint32_t amask;
    Py_buffer ram;
    Py_buffer rom;
    uint32_t rom_lo;
    PyObject *rd, *wr, *sync;
    int budget;
    int base;
    int running;
    int broke;
    int irq;
    int nreg;
    uint32_t reg_lo[16];
    Py_buffer reg[16];
    unsigned long touches;
} Core;

static Core *cur = NULL;
static int started = 0;

static void activate(Core *c)
{
    if (cur == c)
        return;
    if (cur)
        m68k_get_context(cur->ctx);
    m68k_set_cpu_type(c->type);
    m68k_set_context(c->ctx);
    cur = c;
}

static void do_sync(void)
{
    PyObject *r;
    if (!cur->sync)
        return;
    r = PyObject_CallFunction(cur->sync, "i", cur->base + cur->budget - m68k_cycles_remaining());
    if (!r)
        PyErr_Clear();
    Py_XDECREF(r);
}

static uint32_t hook_read(uint32_t a, int size)
{
    PyObject *r;
    uint32_t v = 0;
    if (a >= 0xC00000 && a < 0xE00000)
        do_sync();
    r = PyObject_CallFunction(cur->rd, "Ii", a, size);
    if (!r) {
        PyErr_Print();
        return 0;
    }
    v = (uint32_t)PyLong_AsUnsignedLongMask(r);
    Py_DECREF(r);
    return v;
}

static void hook_write(uint32_t a, int size, uint32_t v)
{
    PyObject *r;
    if (a >= 0xC00000 && a < 0xE00000)
        do_sync();
    r = PyObject_CallFunction(cur->wr, "IiI", a, size, v);
    if (!r) {
        PyErr_Print();
        return;
    }
    Py_DECREF(r);
}

#define RAMN ((uint32_t)cur->ram.len)

static uint8_t *region(uint32_t a, uint32_t n)
{
    int i;
    for (i = 0; i < cur->nreg; i++) {
        uint32_t o = a - cur->reg_lo[i];
        if (o < (uint32_t)cur->reg[i].len && (uint64_t)o + n <= (uint64_t)cur->reg[i].len) {
            cur->touches++;
            return (uint8_t *)cur->reg[i].buf + o;
        }
    }
    return NULL;
}
#define ROMN ((uint32_t)cur->rom.len)

unsigned int m68k_read_memory_8(unsigned int a)
{
    uint32_t o;
    a &= cur->amask;
    if (a < RAMN)
        return ((uint8_t *)cur->ram.buf)[a];
    o = a - cur->rom_lo;
    if (o < ROMN)
        return ((uint8_t *)cur->rom.buf)[o];
    {
        uint8_t *p = region(a, 1);
        if (p)
            return p[0];
    }
    return hook_read(a, 0) & 0xFF;
}

unsigned int m68k_read_memory_16(unsigned int a)
{
    uint32_t o;
    a &= cur->amask;
    if ((uint64_t)a + 2 <= RAMN) {
        uint8_t *p = (uint8_t *)cur->ram.buf + a;
        return (p[0] << 8) | p[1];
    }
    o = a - cur->rom_lo;
    if ((uint64_t)o + 2 <= ROMN) {
        uint8_t *p = (uint8_t *)cur->rom.buf + o;
        return (p[0] << 8) | p[1];
    }
    {
        uint8_t *p = region(a, 2);
        if (p)
            return (p[0] << 8) | p[1];
    }
    return hook_read(a, 1) & 0xFFFF;
}

unsigned int m68k_read_memory_32(unsigned int a)
{
    uint32_t o;
    a &= cur->amask;
    if ((uint64_t)a + 4 <= RAMN) {
        uint8_t *p = (uint8_t *)cur->ram.buf + a;
        return ((uint32_t)p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3];
    }
    o = a - cur->rom_lo;
    if ((uint64_t)o + 4 <= ROMN) {
        uint8_t *p = (uint8_t *)cur->rom.buf + o;
        return ((uint32_t)p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3];
    }
    {
        uint8_t *p = region(a, 4);
        if (p)
            return ((uint32_t)p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3];
    }
    return hook_read(a, 2);
}

unsigned int m68k_read_immediate_16(unsigned int a) { return m68k_read_memory_16(a); }
unsigned int m68k_read_immediate_32(unsigned int a) { return m68k_read_memory_32(a); }
unsigned int m68k_read_disassembler_8(unsigned int a) { return m68k_read_memory_8(a); }
unsigned int m68k_read_disassembler_16(unsigned int a) { return m68k_read_memory_16(a); }
unsigned int m68k_read_disassembler_32(unsigned int a) { return m68k_read_memory_32(a); }

void m68k_write_memory_8(unsigned int a, unsigned int v)
{
    a &= cur->amask;
    if (a < RAMN)
        ((uint8_t *)cur->ram.buf)[a] = (uint8_t)v;
    else {
        uint8_t *p = region(a, 1);
        if (p)
            p[0] = (uint8_t)v;
        else
            hook_write(a, 0, v & 0xFF);
    }
}

void m68k_write_memory_16(unsigned int a, unsigned int v)
{
    a &= cur->amask;
    if ((uint64_t)a + 2 <= RAMN) {
        uint8_t *p = (uint8_t *)cur->ram.buf + a;
        p[0] = (uint8_t)(v >> 8);
        p[1] = (uint8_t)v;
    } else {
        uint8_t *p = region(a, 2);
        if (p) {
            p[0] = (uint8_t)(v >> 8);
            p[1] = (uint8_t)v;
        } else
            hook_write(a, 1, v & 0xFFFF);
    }
}

void m68k_write_memory_32(unsigned int a, unsigned int v)
{
    a &= cur->amask;
    if ((uint64_t)a + 4 <= RAMN) {
        uint8_t *p = (uint8_t *)cur->ram.buf + a;
        p[0] = (uint8_t)(v >> 24);
        p[1] = (uint8_t)(v >> 16);
        p[2] = (uint8_t)(v >> 8);
        p[3] = (uint8_t)v;
    } else {
        uint8_t *p = region(a, 4);
        if (p) {
            p[0] = (uint8_t)(v >> 24);
            p[1] = (uint8_t)(v >> 16);
            p[2] = (uint8_t)(v >> 8);
            p[3] = (uint8_t)v;
        } else
            hook_write(a, 2, v);
    }
}

void m68k_write_memory_32_pd(unsigned int a, unsigned int v)
{
    m68k_write_memory_32(a, (v << 16) | (v >> 16));
}

static int core_init(Core *self, PyObject *args, PyObject *kw)
{
    static char *kws[] = {"model", "ram", "rd", "wr", NULL};
    int model;
    PyObject *ram, *rd, *wr;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "iOOO", kws, &model, &ram, &rd, &wr))
        return -1;
    if (PyObject_GetBuffer(ram, &self->ram, PyBUF_WRITABLE) < 0)
        return -1;
    Py_INCREF(rd);
    Py_INCREF(wr);
    self->rd = rd;
    self->wr = wr;
    switch (model) {
    case 68000: self->type = M68K_CPU_TYPE_68000; self->amask = 0xFFFFFF; break;
    case 68010: self->type = M68K_CPU_TYPE_68010; self->amask = 0xFFFFFF; break;
    case 68020: self->type = M68K_CPU_TYPE_68020; self->amask = 0xFFFFFFFF; break;
    case 68030: self->type = M68K_CPU_TYPE_68030; self->amask = 0xFFFFFFFF; break;
    default: self->type = M68K_CPU_TYPE_68040; self->amask = 0xFFFFFFFF; break;
    }
    if (!started) {
        m68k_init();
        started = 1;
    }
    self->ctx = PyMem_Malloc(m68k_context_size());
    if (!self->ctx) {
        PyErr_NoMemory();
        return -1;
    }
    memset(self->ctx, 0, m68k_context_size());
    if (cur)
        m68k_get_context(cur->ctx);
    cur = NULL;
    m68k_set_cpu_type(self->type);
    m68k_get_context(self->ctx);
    cur = self;
    return 0;
}

static void core_dealloc(Core *self)
{
    if (cur == self)
        cur = NULL;
    if (self->ram.obj)
        PyBuffer_Release(&self->ram);
    if (self->rom.obj)
        PyBuffer_Release(&self->rom);
    while (self->nreg > 0)
        PyBuffer_Release(&self->reg[--self->nreg]);
    Py_XDECREF(self->rd);
    Py_XDECREF(self->wr);
    Py_XDECREF(self->sync);
    PyMem_Free(self->ctx);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *core_set_rom(Core *self, PyObject *args)
{
    PyObject *b;
    unsigned long lo;
    if (!PyArg_ParseTuple(args, "Ok", &b, &lo))
        return NULL;
    if (self->rom.obj)
        PyBuffer_Release(&self->rom);
    memset(&self->rom, 0, sizeof(self->rom));
    if (b != Py_None && PyObject_GetBuffer(b, &self->rom, PyBUF_SIMPLE) < 0)
        return NULL;
    self->rom_lo = (uint32_t)lo;
    Py_RETURN_NONE;
}

static PyObject *core_add_ram(Core *self, PyObject *args)
{
    PyObject *b;
    unsigned long lo;
    if (!PyArg_ParseTuple(args, "kO", &lo, &b))
        return NULL;
    if (self->nreg >= 16) {
        PyErr_SetString(PyExc_ValueError, "too many RAM regions");
        return NULL;
    }
    if (PyObject_GetBuffer(b, &self->reg[self->nreg], PyBUF_WRITABLE) < 0)
        return NULL;
    self->reg_lo[self->nreg++] = (uint32_t)lo;
    Py_RETURN_NONE;
}

static PyObject *core_get_touches(Core *self, void *c) { return PyLong_FromUnsignedLong(self->touches); }

static PyObject *core_set_sync(Core *self, PyObject *arg)
{
    Py_XDECREF(self->sync);
    self->sync = arg == Py_None ? NULL : arg;
    Py_XINCREF(self->sync);
    Py_RETURN_NONE;
}

static PyObject *core_reset(Core *self, PyObject *args)
{
    unsigned long pc, sp;
    if (!PyArg_ParseTuple(args, "kk", &pc, &sp))
        return NULL;
    activate(self);
    m68k_pulse_reset();
    m68k_set_reg(M68K_REG_SP, (unsigned int)sp);
    m68k_set_reg(M68K_REG_PC, (unsigned int)pc);
    m68k_set_reg(M68K_REG_SR, 0x2700);
    self->irq = 0;
    m68k_set_irq(0);
    Py_RETURN_NONE;
}

static PyObject *core_execute(Core *self, PyObject *args)
{
    int cycles, used, total = 0;
    if (!PyArg_ParseTuple(args, "i", &cycles))
        return NULL;
    activate(self);
    self->running = 1;
    while (cycles > 0) {
        self->budget = cycles;
        self->base = total;
        self->broke = 0;
        used = m68k_execute(cycles);
        if (PyErr_Occurred()) {
            self->running = 0;
            return NULL;
        }
        total += used;
        cycles -= used;
        if (!self->broke || used <= 0)
            break;
    }
    self->running = 0;
    return PyLong_FromLong(total);
}

static PyObject *core_get_irq(Core *self, void *c) { return PyLong_FromLong(self->irq); }

static int core_set_irq(Core *self, PyObject *v, void *c)
{
    long l = PyLong_AsLong(v);
    if (l == -1 && PyErr_Occurred())
        return -1;
    activate(self);
    if (self->running && l > self->irq) {
        self->broke = 1;
        m68k_end_timeslice();
    }
    self->irq = (int)l;
    m68k_set_irq((unsigned int)l);
    return 0;
}

static PyObject *core_get_stopped(Core *self, void *c)
{
    activate(self);
    return PyBool_FromLong(m68k_is_stopped());
}

static PyObject *core_get_reg(Core *self, PyObject *args)
{
    int r;
    if (!PyArg_ParseTuple(args, "i", &r))
        return NULL;
    activate(self);
    return PyLong_FromUnsignedLong(m68k_get_reg(NULL, (m68k_register_t)r));
}

static PyObject *core_set_reg(Core *self, PyObject *args)
{
    int r;
    unsigned long v;
    if (!PyArg_ParseTuple(args, "ik", &r, &v))
        return NULL;
    activate(self);
    m68k_set_reg((m68k_register_t)r, (unsigned int)v);
    Py_RETURN_NONE;
}

static PyObject *core_set_amask(Core *self, PyObject *args) {
    unsigned int m;
    if (!PyArg_ParseTuple(args, "I", &m)) return NULL;
    self->amask = m;
    Py_RETURN_NONE;
}

static PyObject *core_set_fpu(Core *self, PyObject *args) {
    int m;
    if (!PyArg_ParseTuple(args, "i", &m)) return NULL;
    m68k_fpu_mode = m;
    Py_RETURN_NONE;
}

static PyMethodDef core_methods[] = {
    {"set_fpu", (PyCFunction)core_set_fpu, METH_VARARGS, "0 none, 1 external, 2 internal"},
    {"set_amask", (PyCFunction)core_set_amask, METH_VARARGS, "address mask, 24-bit addressing"},
    {"set_rom", (PyCFunction)core_set_rom, METH_VARARGS, "ROM bytes and base address"},
    {"add_ram", (PyCFunction)core_add_ram, METH_VARARGS, "add_ram(base, buffer)"},
    {"set_sync", (PyCFunction)core_set_sync, METH_O, "callable(cycles_done) before hooked access"},
    {"reset", (PyCFunction)core_reset, METH_VARARGS, "reset(pc, sp)"},
    {"execute", (PyCFunction)core_execute, METH_VARARGS, "execute(cycles) -> cycles used"},
    {"reg", (PyCFunction)core_get_reg, METH_VARARGS, "reg(n)"},
    {"set_reg", (PyCFunction)core_set_reg, METH_VARARGS, "set_reg(n, v)"},
    {NULL}
};

static PyGetSetDef core_getset[] = {
    {"irq_level", (getter)core_get_irq, (setter)core_set_irq, "interrupt level", NULL},
    {"stopped", (getter)core_get_stopped, NULL, "STOP or halt state", NULL},
    {"touches", (getter)core_get_touches, NULL, "direct RAM region accesses", NULL},
    {NULL}
};

static PyTypeObject CoreType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "musashi_ext.Core",
    .tp_basicsize = sizeof(Core),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)core_init,
    .tp_dealloc = (destructor)core_dealloc,
    .tp_methods = core_methods,
    .tp_getset = core_getset,
};

static struct PyModuleDef mod = {PyModuleDef_HEAD_INIT, "musashi_ext", "Musashi 68k core", -1, NULL};

PyMODINIT_FUNC PyInit_musashi_ext(void)
{
    PyObject *m;
    if (PyType_Ready(&CoreType) < 0)
        return NULL;
    m = PyModule_Create(&mod);
    if (!m)
        return NULL;
    Py_INCREF(&CoreType);
    PyModule_AddObject(m, "Core", (PyObject *)&CoreType);
    PyModule_AddIntConstant(m, "REG_D0", M68K_REG_D0);
    PyModule_AddIntConstant(m, "REG_A0", M68K_REG_A0);
    PyModule_AddIntConstant(m, "REG_PC", M68K_REG_PC);
    PyModule_AddIntConstant(m, "REG_SR", M68K_REG_SR);
    PyModule_AddIntConstant(m, "REG_SP", M68K_REG_SP);
    return m;
}
