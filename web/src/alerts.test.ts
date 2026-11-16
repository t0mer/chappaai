import { beforeEach, describe, expect, it, vi } from "vitest";

const fire = vi.fn();
const toastFire = vi.fn();
// Like SweetAlert2: fire() resolves when the popup starts closing, didDestroy runs after teardown.
vi.mock("sweetalert2", () => ({
  default: {
    fire: (...a: unknown[]) => {
      const p = Promise.resolve(fire(...a));
      void p.then(() => setTimeout(() => (a[0] as { didDestroy?: () => void }).didDestroy?.(), 0));
      return p;
    },
    mixin: () => ({ fire: (...a: unknown[]) => toastFire(...a) }),
  },
}));

import { confirm, errorDialog, toast } from "./alerts";

beforeEach(() => vi.clearAllMocks());

describe("alerts", () => {
  it("confirm resolves true only when confirmed", async () => {
    fire.mockResolvedValueOnce({ isConfirmed: true });
    expect(await confirm({ title: "Sure?", text: "body", confirmText: "Do it", danger: true })).toBe(true);
    const opts = fire.mock.calls[0][0];
    expect(opts).toMatchObject({ titleText: "Sure?", text: "body", confirmButtonText: "Do it", showCancelButton: true, focusCancel: true });
    fire.mockResolvedValueOnce({ isConfirmed: false, isDismissed: true });
    expect(await confirm({ title: "x" })).toBe(false);
  });

  it("toast helpers pass the message and icon", () => {
    toast.success("Saved");
    toast.error("Boom");
    toast.info("FYI");
    expect(toastFire.mock.calls.map((c) => [c[0].icon, c[0].titleText])).toEqual([
      ["success", "Saved"],
      ["error", "Boom"],
      ["info", "FYI"],
    ]);
  });

  it("errorDialog shows title and message", async () => {
    fire.mockResolvedValueOnce({});
    await errorDialog("Failed", "nope");
    expect(fire.mock.calls[0][0]).toMatchObject({ icon: "error", titleText: "Failed", text: "nope" });
  });
});
