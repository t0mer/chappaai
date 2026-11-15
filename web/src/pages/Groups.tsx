import { useRef, useState, type FormEvent } from "react";
import { Users } from "lucide-react";
import { api } from "../api";
import { confirm, toast } from "../alerts";
import EditGroupDialog from "../components/EditGroupDialog";
import { Button } from "../components/ui/button";
import { EmptyState } from "../components/ui/empty-state";
import { Input, Select } from "../components/ui/field";
import { FilterChip } from "../components/ui/filter-chip";
import { InlineError } from "../components/ui/inline-error";
import { PageHeader } from "../components/ui/page-header";
import { Skeleton } from "../components/ui/skeleton";
import { Switch } from "../components/ui/switch";
import { useMediaQuery, XL_QUERY } from "../hooks/useMediaQuery";
import type { Group, GroupPatch, GroupSort } from "../types";
import { useLoad, useLoadError } from "../useLoad";

const PAGE = 50;

type Managed = "all" | "managed" | "unmanaged";
const FILTERS: { value: Managed; label: string }[] = [
  { value: "all", label: "All" },
  { value: "managed", label: "Enabled" },
  { value: "unmanaged", label: "Disabled" },
];

const groupLabel = (g: Group) => g.display_name || g.group_name || g.group_jid;

/**
 * Dialog openers carry a stable key, so focus can return to the opener even when the table/cards
 * swap (a viewport resize while a dialog is open) replaced the element that opened it.
 */
const openerKey = (g: Group) => `edit:${g.group_jid}`;

/** Everything a row or card needs to act on one group. */
interface RowProps {
  group: Group;
  saving: boolean;
  onToggleManaged: (g: Group) => void;
  onEdit: (g: Group) => void;
}

function GroupName({ g }: { g: Group }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <strong className="font-medium" dir="auto"><bdi>{groupLabel(g)}</bdi></strong>
      <div className="break-all text-xs text-muted-foreground">
        {g.display_name && g.group_name && <>WhatsApp: <bdi>{g.group_name}</bdi> · </>}<bdi className="jid">{g.group_jid}</bdi>
      </div>
      {g.group_topic && <div className="text-xs text-muted-foreground" dir="auto"><bdi>{g.group_topic}</bdi></div>}
      <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {g.community_keys.length > 0 && <span>Community keys: <bdi>{g.community_keys.join(", ")}</bdi></span>}
        <span>{g.message_count} {g.message_count === 1 ? "message" : "messages"}</span>
      </div>
    </div>
  );
}

/** Larger hit area (44px) without changing the switch's look. */
const SWITCH_HIT = "relative after:absolute after:-inset-2.5 after:content-['']";

function EnabledSwitch({ group: g, saving, onToggleManaged }: RowProps) {
  return <Switch className={SWITCH_HIT} checked={g.managed} onCheckedChange={() => onToggleManaged(g)} aria-label={`Enabled for ${g.group_jid}`} disabled={saving} />;
}

function GroupTableRow(p: RowProps) {
  const g = p.group;
  return (
    <tr className="border-t align-middle hover:bg-surface-2/60">
      <td className="w-full px-3 py-1.5"><GroupName g={g} /></td>
      <td className="px-3 py-1.5"><EnabledSwitch {...p} /></td>
      <td className="px-3 py-1.5 text-end"><Button size="table" data-opener={openerKey(g)} onClick={() => p.onEdit(g)} aria-label={`Edit ${g.group_jid}`}>Edit</Button></td>
    </tr>
  );
}

/** A switch with its visible label, so phones show what each one does. */
function SwitchRow({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="flex min-h-11 items-center gap-2 text-sm">{children}{label}</label>;
}

function GroupCard(p: RowProps) {
  const g = p.group;
  return (
    <li className="flex flex-col gap-2 rounded-lg border bg-surface p-3">
      <GroupName g={g} />
      <div className="flex flex-wrap gap-x-6">
        <SwitchRow label="Enabled"><EnabledSwitch {...p} /></SwitchRow>
      </div>
      <div className="grid gap-2">
        <Button size="lg" data-opener={openerKey(g)} onClick={() => p.onEdit(g)} aria-label={`Edit ${g.group_jid}`}>Edit</Button>
      </div>
    </li>
  );
}

const HEADERS = ["Group", "Enabled"];

function LoadingRows({ desktop }: { desktop: boolean }) {
  const label = <span className="sr-only">Loading…</span>;
  if (desktop) {
    return (
      <div role="status" className="rounded-lg border bg-surface p-3">
        {label}
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="my-2 h-[72px]" />)}
      </div>
    );
  }
  return (
    <div role="status" className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {label}
      {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-72 rounded-lg" />)}
    </div>
  );
}

export default function Groups() {
  const desktop = useMediaQuery(XL_QUERY);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [managed, setManaged] = useState<Managed>("all");
  const [sort, setSort] = useState<GroupSort>("name");
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Group | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [savingJid, setSavingJid] = useState<string | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);

  /** Focus the current opener of a closed dialog, or the search box if the group left the list. */
  function returnFocus(key: string) {
    const opener = Array.from(document.querySelectorAll<HTMLElement>("[data-opener]")).find((el) => el.dataset.opener === key);
    (opener ?? searchInput.current)?.focus();
  }

  const { data, error, loading, reload } = useLoad(
    () =>
      api.listGroups({
        search: query,
        managed: managed === "all" ? undefined : managed === "managed",
        sort,
        limit: PAGE,
        offset,
      }),
    [query, managed, sort, offset],
  );
  const inlineError = useLoadError(error, data !== null);

  const label = groupLabel;

  /** Save a patch. Failures show inline in the edit dialog, otherwise as a toast. */
  async function save(group: Group, patch: GroupPatch, inline = false): Promise<boolean> {
    setDialogError(null);
    setSavingJid(group.group_jid);
    try {
      await api.patchGroup(group.group_jid, patch);
      toast.success(`Saved ${label(group)}`);
      await reload();
      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      if (inline) setDialogError(message);
      else toast.error(message);
      await reload();
      return false;
    } finally {
      setSavingJid(null);
    }
  }

  async function toggleManaged(group: Group) {
    if (!group.managed) {
      const ok = await confirm({
        title: `Enable "${label(group)}"?`,
        text: "New messages from this group will be stored and processed.",
        confirmText: "Enable",
      });
      if (!ok) return;
    }
    void save(group, { managed: !group.managed });
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    setOffset(0);
    setQuery(search.trim());
  }

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const rowProps = (group: Group): RowProps => ({
    group,
    saving: savingJid === group.group_jid,
    onToggleManaged: (g) => void toggleManaged(g),
    onEdit: setEditing,
  });

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Groups" description="Choose which groups are tracked and how they are named." />
      <form role="search" aria-label="Group filters" className="flex flex-col gap-3" onSubmit={onSearch}>
        <div className="flex flex-wrap gap-2">
          <Input ref={searchInput} className="min-w-0 flex-1 basis-56" placeholder="Search name, topic or JID" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search groups" />
          <Button type="submit" variant="primary" size="lg">Search</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Filter" className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <FilterChip key={f.value} active={managed === f.value} onClick={() => { setOffset(0); setManaged(f.value); }}>{f.label}</FilterChip>
            ))}
          </div>
          <div className="w-full sm:ms-auto sm:w-56">
            <Select value={sort} onChange={(e) => { setOffset(0); setSort(e.target.value as GroupSort); }} aria-label="Sort">
              <option value="name">Name</option>
              <option value="-message_count">Most messages</option>
              <option value="-created_at">Newest</option>
            </Select>
          </div>
        </div>
        <p aria-live="polite" className="text-sm text-muted-foreground">{total} groups</p>
      </form>
      {/*
        A stable wrapper around everything that swaps (error, loading, empty, table <-> cards). An open
        modal dialog hides the page from assistive tech when it opens; elements created later inside
        this wrapper (e.g. the cards after a resize) inherit that, instead of appearing un-hidden.
      */}
      <div className="flex flex-col gap-5">
      {inlineError && <InlineError>{inlineError}</InlineError>}
      {loading && !data ? (
        <LoadingRows desktop={desktop} />
      ) : data && items.length === 0 ? (
        <div className="rounded-lg border bg-surface">
          <EmptyState icon={Users} title="No groups match.">Try a different search or filter.</EmptyState>
        </div>
      ) : !data ? null : desktop ? (
        <div className="relative overflow-x-auto rounded-lg border bg-surface">
          <table className="w-full text-start text-sm" aria-label="Groups">
            <thead>
              <tr className="text-start">
                {HEADERS.map((h) => <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 text-start font-medium text-muted-foreground">{h}</th>)}
                <th scope="col" className="relative px-3 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((g) => <GroupTableRow key={g.group_jid} {...rowProps(g)} />)}
            </tbody>
          </table>
        </div>
      ) : (
        <ul role="list" aria-label="Groups" className="m-0 grid list-none grid-cols-1 gap-3 p-0 md:grid-cols-2">
          {items.map((g) => <GroupCard key={g.group_jid} {...rowProps(g)} />)}
        </ul>
      )}
      <div className="flex items-center gap-2">
        <Button size="lg" className="lg:min-h-9" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
        <Button size="lg" className="lg:min-h-9" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
      </div>
      </div>
      {editing && (
        <EditGroupDialog
          group={editing}
          returnFocus={() => returnFocus(openerKey(editing))}
          error={dialogError}
          saving={savingJid === editing.group_jid}
          onCancel={() => { setDialogError(null); setEditing(null); }}
          onSave={async (patch) => {
            if (await save(editing, patch, true)) setEditing(null);
          }}
        />
      )}
    </div>
  );
}
