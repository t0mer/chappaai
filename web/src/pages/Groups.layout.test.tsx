import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Groups from "./Groups";
import { api } from "../api";
import { mockViewport } from "../hooks/mockViewport";
import type { Group } from "../types";

vi.mock("../api", async (orig) => {
  const actual = await orig<typeof import("../api")>();
  return { ...actual, api: { listGroups: vi.fn(), patchGroup: vi.fn() } };
});
vi.mock("../alerts");
import { confirm, toast } from "../alerts";

const base: Group = {
  group_jid: "1@g.us", group_name: "WA name", display_name: null, group_topic: null,
  owner_jid: null, managed: false, community_keys: ["fam"], message_count: 12,
};

function setup(groups: Group[]) {
  vi.mocked(api.listGroups).mockResolvedValue({ items: groups, total: groups.length });
  vi.mocked(api.patchGroup).mockImplementation(async (jid, patch) => ({ ...groups.find((g) => g.group_jid === jid)!, ...patch }) as Group);
  return render(<Groups />);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(confirm).mockResolvedValue(true);
});

describe("Groups toolbar (table, from 1280px)", () => {
  beforeEach(() => void mockViewport(1280));

  it("searches on submit with the trimmed text and resets the offset", async () => {
    setup([base]);
    await screen.findByRole("table", { name: "Groups" });
    await userEvent.type(screen.getByRole("textbox", { name: "Search groups" }), "  fam  ");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(api.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ search: "fam", offset: 0 })));
  });

  it("filters with chips, exposing the active one with aria-pressed", async () => {
    setup([base]);
    await screen.findByRole("table");
    const group = screen.getByRole("group", { name: "Filter" });
    const chip = (n: string) => within(group).getByRole("button", { name: n });
    expect(chip("All")).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(chip("Enabled"));
    await waitFor(() => expect(api.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ managed: true })));
    expect(chip("Enabled")).toHaveAttribute("aria-pressed", "true");
    expect(chip("All")).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(chip("Disabled"));
    await waitFor(() => expect(api.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ managed: false })));
    await userEvent.click(chip("All"));
    await waitFor(() => expect(api.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ managed: undefined })));
  });

  it("announces the count politely so filter results are heard", async () => {
    setup([base]);
    const count = await screen.findByText("1 groups");
    expect(count).toHaveAttribute("aria-live", "polite");
  });

  it("shows the total count", async () => {
    vi.mocked(api.listGroups).mockResolvedValue({ items: [base], total: 7 });
    render(<Groups />);
    expect(await screen.findByText("7 groups")).toBeInTheDocument();
  });

  it("renders Enabled as a named switch reflecting state", async () => {
    setup([{ ...base, managed: true }, { ...base, group_jid: "2@g.us" }]);
    expect(await screen.findByRole("switch", { name: "Enabled for 1@g.us" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Enabled for 2@g.us" })).not.toBeChecked();
  });

  it("disables the switch while saving", async () => {
    setup([{ ...base, managed: true }]);
    let release!: () => void;
    vi.mocked(api.patchGroup).mockReturnValueOnce(new Promise((r) => { release = () => r(base); }));
    await userEvent.click(await screen.findByRole("switch", { name: /enabled/i }));
    expect(screen.getByRole("switch", { name: /enabled/i })).toBeDisabled();
    release();
    await waitFor(() => expect(screen.getByRole("switch", { name: /enabled/i })).toBeEnabled());
  });

  it("does not enable the group when the confirm is declined", async () => {
    vi.mocked(confirm).mockResolvedValue(false);
    setup([base]);
    await userEvent.click(await screen.findByRole("switch", { name: /enabled/i }));
    expect(vi.mocked(confirm).mock.calls[0][0]).toMatchObject({ confirmText: "Enable" });
    expect(api.patchGroup).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("renders Hebrew names inside bdi and lets the text direction follow the content", async () => {
    setup([{ ...base, display_name: "קבוצת בדיקה", group_topic: "נושא" }]);
    const name = await screen.findByText("קבוצת בדיקה");
    expect(name.tagName).toBe("BDI");
    expect(name.parentElement).toHaveAttribute("dir", "auto");
    expect(screen.getByText("נושא").tagName).toBe("BDI");
    expect(screen.getByText("1@g.us").tagName).toBe("BDI");
  });

  it("shows loading skeleton rows, then the table", async () => {
    let resolve!: (v: { items: Group[]; total: number }) => void;
    vi.mocked(api.listGroups).mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<Groups />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    resolve({ items: [base], total: 1 });
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows an empty state with an icon", async () => {
    setup([]);
    const msg = await screen.findByText("No groups match.");
    expect(msg.parentElement?.querySelector("svg")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a failed first load only inline: no toast, no empty table", async () => {
    vi.mocked(api.listGroups).mockRejectedValue(new Error("server down"));
    render(<Groups />);
    expect(await screen.findByRole("alert")).toHaveTextContent("server down");
    expect(toast.error).not.toHaveBeenCalled();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("toasts only when a refresh fails while rows are on screen", async () => {
    setup([base]);
    await screen.findByRole("table", { name: "Groups" });
    vi.mocked(api.listGroups).mockRejectedValue(new Error("refresh failed"));
    await userEvent.click(screen.getByRole("button", { name: "Enabled" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("refresh failed"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Groups" })).toBeInTheDocument();
  });
});

describe("Groups on tablets", () => {
  it("shows cards with 44px controls below 1280px (the table does not fit beside the sidebar)", async () => {
    mockViewport(800);
    setup([base]);
    expect(await screen.findByRole("button", { name: "Edit 1@g.us" })).toHaveClass("min-h-11");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("Groups at phone width", () => {
  beforeEach(() => void mockViewport(390));

  it("renders cards instead of a table, with the same accessible names and no duplicates", async () => {
    setup([{ ...base, display_name: "My alias" }]);
    const list = await screen.findByRole("list", { name: "Groups" });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getAllByRole("switch", { name: /enabled for 1@g\.us/i })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Edit 1@g.us" })).toHaveLength(1);
    expect(within(list).getByText("Enabled")).toBeInTheDocument();
    expect(list).toHaveTextContent("Community keys: fam");
    expect(list).toHaveTextContent("12 messages");
    expect(list).toHaveTextContent("fam");
  });

  it("puts the switch and the Edit button on separate rows", async () => {
    setup([base]);
    const li = (await screen.findAllByRole("listitem"))[0];
    const enabled = within(li).getByRole("switch", { name: /enabled/i });
    const edit = within(li).getByRole("button", { name: /^Edit/ });
    expect(enabled.closest("div")!.contains(edit)).toBe(false);
  });

  it("pluralises the message count", async () => {
    setup([{ ...base, message_count: 1 }, { ...base, group_jid: "2@g.us", group_name: "Two", message_count: 2 }]);
    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("1 message");
    expect(items[0]).not.toHaveTextContent("1 messages");
    expect(items[1]).toHaveTextContent("2 messages");
  });

  it("shows card-shaped skeletons while loading on phones", async () => {
    vi.mocked(api.listGroups).mockReturnValue(new Promise(() => {}));
    render(<Groups />);
    const status = screen.getByRole("status");
    expect(status.className).toContain("grid-cols-1");
    expect(status.className).toContain("md:grid-cols-2");
    expect(status.querySelectorAll("div[aria-hidden]")).toHaveLength(4);
  });

  it("uses cards below 1280px, including tablet widths", async () => {
    mockViewport(1024);
    setup([base]);
    expect(await screen.findByRole("list", { name: "Groups" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps meta in the Group cell of the table and only three columns", async () => {
    mockViewport(1280);
    setup([base]);
    const headers = (await screen.findAllByRole("columnheader")).map((h) => h.textContent);
    expect(headers).toEqual(["Group", "Enabled", "Actions"]);
    const row = screen.getByRole("row", { name: /WA name/ });
    expect(row).toHaveTextContent("Community keys: fam");
    expect(row).toHaveTextContent("12 messages");
  });

  it("keeps list semantics (role=list) on the card list", async () => {
    setup([base]);
    expect(await screen.findByRole("list", { name: "Groups" })).toHaveAttribute("role", "list");
  });

  it("keeps the behaviour: confirm then PATCH, revert on failure", async () => {
    setup([base]);
    await userEvent.click(await screen.findByRole("switch", { name: /enabled/i }));
    await waitFor(() => expect(api.patchGroup).toHaveBeenCalledWith("1@g.us", { managed: true }));
    vi.mocked(api.patchGroup).mockRejectedValueOnce(new Error("boom"));
    await userEvent.click(screen.getByRole("switch", { name: /enabled/i }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
    await waitFor(() => expect(screen.getByRole("switch", { name: /enabled/i })).not.toBeChecked());
  });

  it("gives touch controls a 44px target and the actions full-width buttons", async () => {
    setup([base]);
    const li = (await screen.findAllByRole("listitem"))[0];
    expect(within(li).getByRole("button", { name: /^Edit/ })).toHaveClass("min-h-11");
    expect(within(li).getByRole("switch", { name: /enabled/i }).className).toContain("after:-inset-2.5");
    expect(screen.getByRole("button", { name: "Next" })).toHaveClass("min-h-11");
    for (const n of ["All", "Enabled", "Disabled"]) {
      expect(screen.getByRole("button", { name: n })).toHaveClass("min-h-11");
    }
  });

  it("shows the empty state, not the card list, when nothing matches", async () => {
    setup([]);
    expect(await screen.findByText("No groups match.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Groups" })).not.toBeInTheDocument();
  });

  it("renders Hebrew names inside bdi on cards", async () => {
    setup([{ ...base, display_name: "קבוצה" }]);
    expect((await screen.findByText("קבוצה")).tagName).toBe("BDI");
  });
});

describe("Groups across a viewport resize", () => {
  const controls = () => ({
    enabled: screen.getAllByRole("switch", { name: /enabled for 1@g\.us/i }),
    edit: screen.getAllByRole("button", { name: "Edit 1@g.us" }),
  });

  it("swaps table and cards without duplicating controls or losing state", async () => {
    const vp = mockViewport(1280);
    // A short page (3 rows) of a larger total keeps Next/Previous meaningful without rendering 50 rows twice.
    const many = Array.from({ length: 3 }, (_, i) => ({ ...base, group_jid: i === 0 ? "1@g.us" : `${i + 100}@g.us` }));
    vi.mocked(api.listGroups).mockResolvedValue({ items: many, total: 120 });
    render(<Groups />);
    await screen.findByRole("table");
    // one change event instead of one per typed character
    fireEvent.change(screen.getByRole("textbox", { name: "Search groups" }), { target: { value: "draft" } });
    await userEvent.click(screen.getByRole("button", { name: "Disabled" }));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(api.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50, managed: false })));

    vp.setWidth(600);
    expect(await screen.findByRole("list", { name: "Groups" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(controls().enabled).toHaveLength(1);
    expect(controls().edit).toHaveLength(1);
    expect(screen.getByRole("textbox", { name: "Search groups" })).toHaveValue("draft");
    expect(screen.getByRole("button", { name: "Disabled" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();

    vp.setWidth(1280);
    expect(await screen.findByRole("table", { name: "Groups" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Groups" })).not.toBeInTheDocument();
    expect(controls().enabled).toHaveLength(1);
    expect(controls().edit).toHaveLength(1);
    expect(screen.getByRole("textbox", { name: "Search groups" })).toHaveValue("draft");
    expect(screen.getByRole("button", { name: "Disabled" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
  });

  it("keeps a pending save in its saving state across a resize", async () => {
    const vp = mockViewport(1280);
    setup([base]);
    let release!: () => void;
    vi.mocked(api.patchGroup).mockReturnValueOnce(new Promise((r) => { release = () => r(base); }));
    await userEvent.click(await screen.findByRole("switch", { name: /enabled/i }));
    expect(screen.getByRole("switch", { name: /enabled/i })).toBeDisabled();
    vp.setWidth(600);
    expect(await screen.findByRole("list", { name: "Groups" })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /enabled/i })).toBeDisabled();
    await act(async () => release());
    await waitFor(() => expect(screen.getByRole("switch", { name: /enabled/i })).toBeEnabled());
  });
});

describe("Groups dialogs across the table/cards swap", () => {
  const user = userEvent.setup({ pointerEventsCheck: 0 }); // Radix sets pointer-events:none on <body>

  async function expectModal(dialog: HTMLElement) {
    // The page behind stays hidden from assistive tech and out of the Tab order after the swap.
    expect(screen.queryByRole("list", { name: "Groups", hidden: false })).not.toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Groups", hidden: true });
    expect(list.closest("[aria-hidden=true]")).not.toBeNull();
    expect(screen.queryByRole("table", { hidden: true })).not.toBeInTheDocument();
    for (let i = 0; i < 15; i++) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    for (let i = 0; i < 5; i++) {
      await user.tab({ shift: true });
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  }

  it("Edit: stays modal and keeps its state when the table becomes cards", async () => {
    const vp = mockViewport(1280);
    setup([base]);
    await user.click(await screen.findByRole("button", { name: "Edit 1@g.us" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit group" });
    await user.type(within(dialog).getByLabelText("Display name"), "Draft");
    vp.setWidth(600);
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(within(dialog).getByLabelText("Display name")).toHaveValue("Draft");
    await expectModal(dialog);
  });

  it("Edit: returns focus to the new opener when the old one was removed by the swap", async () => {
    const opener = "Edit 1@g.us";
    const vp = mockViewport(1280);
    setup([base]);
    const old = await screen.findByRole("button", { name: opener });
    await user.click(old);
    await screen.findByRole("dialog");
    vp.setWidth(600);
    expect(old.isConnected).toBe(false);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const fresh = screen.getByRole("button", { name: opener });
    expect(fresh.closest("li")).not.toBeNull();
    await waitFor(() => expect(fresh).toHaveFocus());
    vp.setWidth(1280);
  });
});
