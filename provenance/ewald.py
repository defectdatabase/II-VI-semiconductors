"""Madelung constant of an arbitrary supercell, by Ewald summation.

alpha_M is defined through the image-charge energy of one point charge q in a periodic cell with
a compensating uniform background:

    E_lattice(q) = q^2 * alpha_M / (2 * eps * L),      L = V^(1/3)

which is the form dft-defects.md J1 uses. The gates are the skill's own: sc 2.837297,
fcc 2.888282, bcc 2.888462, and gamma-independence to the 6th decimal. alpha_M must come from
the ACTUAL supercell -- never the primitive cell, and never another host's (that hard-coded
constant is the J4 bug).
"""
import math

HARTREE_ANG = 14.399645478425668   # e^2/(4 pi eps0) in eV*Angstrom


def _recip(a):
    (a1, a2, a3) = a
    v = (a1[0] * (a2[1] * a3[2] - a2[2] * a3[1])
         - a1[1] * (a2[0] * a3[2] - a2[2] * a3[0])
         + a1[2] * (a2[0] * a3[1] - a2[1] * a3[0]))
    def cross(u, w):
        return (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    b1 = tuple(2 * math.pi * c / v for c in cross(a2, a3))
    b2 = tuple(2 * math.pi * c / v for c in cross(a3, a1))
    b3 = tuple(2 * math.pi * c / v for c in cross(a1, a2))
    return (b1, b2, b3), abs(v)


def madelung(cell, gamma=None, rcut=None, gcut=None):
    """cell = 3x3 lattice vectors in Angstrom. Returns (alpha_M, L, V)."""
    B, V = _recip(cell)
    L = V ** (1.0 / 3.0)
    if gamma is None:
        gamma = 2.2 / L                      # splitting parameter, in 1/Angstrom
    if rcut is None:
        rcut = 9.0 / gamma
    if gcut is None:
        gcut = 9.0 * gamma

    # how many cells to span to cover rcut / gcut
    def spans(vecs, cut):
        out = []
        for v in vecs:
            n = math.sqrt(sum(c * c for c in v))
            out.append(int(cut / n) + 2)
        return out

    nr = spans(cell, rcut)
    ng = spans(B, gcut)

    real = 0.0
    for i in range(-nr[0], nr[0] + 1):
        for j in range(-nr[1], nr[1] + 1):
            for k in range(-nr[2], nr[2] + 1):
                if i == j == k == 0:
                    continue
                x = i * cell[0][0] + j * cell[1][0] + k * cell[2][0]
                y = i * cell[0][1] + j * cell[1][1] + k * cell[2][1]
                z = i * cell[0][2] + j * cell[1][2] + k * cell[2][2]
                r = math.sqrt(x * x + y * y + z * z)
                if r < rcut:
                    real += math.erfc(gamma * r) / r

    recip = 0.0
    for i in range(-ng[0], ng[0] + 1):
        for j in range(-ng[1], ng[1] + 1):
            for k in range(-ng[2], ng[2] + 1):
                if i == j == k == 0:
                    continue
                gx = i * B[0][0] + j * B[1][0] + k * B[2][0]
                gy = i * B[0][1] + j * B[1][1] + k * B[2][1]
                gz = i * B[0][2] + j * B[1][2] + k * B[2][2]
                g2 = gx * gx + gy * gy + gz * gz
                if g2 < gcut * gcut:
                    recip += math.exp(-g2 / (4 * gamma * gamma)) / g2
    recip *= 4 * math.pi / V

    self_term = -2 * gamma / math.sqrt(math.pi)
    background = -math.pi / (gamma * gamma * V)

    xi = real + recip + self_term + background
    alpha_M = -xi * L
    return alpha_M, L, V


def _cubic(a):
    return [[a, 0.0, 0.0], [0.0, a, 0.0], [0.0, 0.0, a]]


def gates(verbose=True):
    """the three reference lattices, and gamma-independence"""
    out = {}
    sc, _, _ = madelung(_cubic(1.0))
    a = 1.0
    fcc = madelung([[0, a / 2, a / 2], [a / 2, 0, a / 2], [a / 2, a / 2, 0]])[0]
    bcc = madelung([[-a / 2, a / 2, a / 2], [a / 2, -a / 2, a / 2], [a / 2, a / 2, -a / 2]])[0]
    g1 = madelung(_cubic(1.0), gamma=2.0)[0]
    g2 = madelung(_cubic(1.0), gamma=4.0)[0]
    out = {"sc": sc, "fcc": fcc, "bcc": bcc, "gamma_spread": abs(g1 - g2)}
    ok = (abs(sc - 2.837297) < 1e-6 and abs(fcc - 2.888282) < 1e-6
          and abs(bcc - 2.888462) < 1e-6 and out["gamma_spread"] < 1e-6)
    if verbose:
        print(f"  Ewald gates: sc {sc:.6f} (2.837297) fcc {fcc:.6f} (2.888282) "
              f"bcc {bcc:.6f} (2.888462) gamma-spread {out['gamma_spread']:.2e} -> "
              f"{'PASS' if ok else 'FAIL'}")
    out["pass"] = ok
    return out


if __name__ == "__main__":
    gates()
