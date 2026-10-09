import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft as IconArrowLeft,
  Building2 as IconBuildingCommunity,
  Plus as IconPlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  createUnitMutationOptions,
  unitOptionsQueryOptions,
  unitsQueryOptions,
} from "@/lib/admin/queries";
import { AdminBadge, AdminDrawer, AdminPage, AdminState } from "./AdminUI";
export function UnitsPage() {
  const units = useQuery(unitsQueryOptions());
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState("overview");
  const [creating, setCreating] = useState(false);
  const open = units.data?.find((unit) => unit.id === selected);
  const members = (unit: NonNullable<typeof units.data>[number]) =>
    unit.groups.reduce((sum, group) => sum + group.members, 0);
  return (
    <AdminPage
      title={open ? open.name : "Đơn vị quản lý"}
      meta={!open && units.data ? `${units.data.length} đơn vị` : undefined}
      action={
        open ? (
          <Button variant="outline" onClick={() => setSelected("")}>
            <IconArrowLeft />
            Đơn vị quản lý
          </Button>
        ) : (
          <Button onClick={() => setCreating(true)}>
            <IconPlus />
            Tạo đơn vị
          </Button>
        )
      }
    >
      {units.isPending || units.error ? (
        <AdminState
          loading={units.isPending}
          error={units.error}
          onRetry={() => void units.refetch()}
        />
      ) : open ? (
        <>
          <div className="ops-admin-tabs-page" aria-label="Chi tiết đơn vị">
            {[
              ["overview", "Tổng quan"],
              ["buildings", "Tòa phụ trách"],
              ["groups", "Nhóm làm việc"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={tab === value}
                onClick={() => setTab(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {tab === "overview" ? (
            <div className="ops-admin-metrics">
              <div className="ops-admin-metric">
                <span>Thành viên nhóm</span>
                <strong>{members(open)}</strong>
              </div>
              <a className="ops-admin-metric" href="/operations/kanban">
                <span>Yêu cầu đang mở</span>
                <strong>{open.open_tickets}</strong>
              </a>
              <div className="ops-admin-metric">
                <span>Nhân viên hiện trường</span>
                <strong>{open.staff}</strong>
              </div>
            </div>
          ) : tab === "buildings" ? (
            <section className="ops-admin-panel">
              <header className="ops-admin-panel-title">
                <h2>Tòa nhà phụ trách</h2>
              </header>
              {open.buildings.map((building) => (
                <div key={building} className="ops-admin-health-row">
                  <IconBuildingCommunity size={16} />
                  <strong>{building}</strong>
                </div>
              ))}
              {!open.buildings.length && (
                <AdminState empty="Đơn vị chưa được giao tòa nhà." />
              )}
            </section>
          ) : (
            <section className="ops-admin-panel">
              <div className="ops-admin-table-wrap">
                <table className="ops-admin-table">
                  <thead>
                    <tr>
                      <th>Nhóm</th>
                      <th>Thành viên</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.groups.map((group) => (
                      <tr key={group.id}>
                        <td>{group.name}</td>
                        <td>{group.members}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!open.groups.length && (
                <AdminState empty="Đơn vị chưa có nhóm làm việc." />
              )}
            </section>
          )}
        </>
      ) : (
        <section className="ops-admin-panel">
          {units.data?.length ? (
            <div className="ops-admin-table-wrap">
              <table className="ops-admin-table">
                <thead>
                  <tr>
                    <th>Đơn vị</th>
                    <th>Tòa phụ trách</th>
                    <th>Thành viên</th>
                    <th>Yêu cầu đang mở</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {units.data.map((unit) => (
                    <tr key={unit.id}>
                      <td>
                        <div className="ops-admin-row-title">
                          <span className="ops-admin-tile">
                            <IconBuildingCommunity size={16} />
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              setSelected(unit.id);
                              setTab("overview");
                            }}
                          >
                            {unit.name}
                          </button>
                        </div>
                      </td>
                      <td>{unit.buildings.join(", ")}</td>
                      <td>{members(unit)}</td>
                      <td>{unit.open_tickets}</td>
                      <td>
                        <AdminBadge
                          tone={unit.status === "active" ? "ok" : "danger"}
                        >
                          {unit.status === "active" ? "Hoạt động" : "Đã dừng"}
                        </AdminBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <AdminState empty="Chưa có đơn vị quản lý. Tạo đơn vị để giao tòa nhà và nhân sự." />
          )}
        </section>
      )}
      {creating && <CreateUnit onClose={() => setCreating(false)} />}
    </AdminPage>
  );
}
function CreateUnit({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const options = useQuery(unitOptionsQueryOptions());
  const create = useMutation(createUnitMutationOptions(queryClient));
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [buildings, setBuildings] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const ready =
    name.trim().length >= 2 &&
    /^[a-z0-9][a-z0-9-]{1,59}$/.test(code) &&
    buildings.length > 0 &&
    categories.length > 0;
  const toggle = (
    id: string,
    values: string[],
    set: (next: string[]) => void,
  ) =>
    set(
      values.includes(id)
        ? values.filter((value) => value !== id)
        : [...values, id],
    );
  const submit = () =>
    create.mutate(
      {
        name: name.trim(),
        code,
        building_ids: buildings,
        category_ids: categories,
      },
      { onSuccess: onClose },
    );
  return (
    <AdminDrawer
      title="Tạo đơn vị quản lý"
      description="Nhóm điều phối của Ban quản lý được tạo cùng đơn vị."
      busy={create.isPending}
      onClose={onClose}
      footer={
        <>
          <Button
            variant="outline"
            disabled={create.isPending}
            onClick={onClose}
          >
            Hủy
          </Button>
          <Button disabled={!ready || create.isPending} onClick={submit}>
            {create.isPending ? "Đang tạo…" : "Tạo đơn vị và nhóm"}
          </Button>
        </>
      }
    >
      <div className="ops-admin-form">
        <label>
          Tên đơn vị
          <Input
            aria-label="Tên đơn vị"
            value={name}
            maxLength={160}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Mã đơn vị
          <Input
            aria-label="Mã đơn vị"
            value={code}
            maxLength={60}
            placeholder="bql-pavilion"
            onChange={(event) => setCode(event.target.value)}
          />
          <small>Chữ thường, số và dấu gạch ngang.</small>
        </label>
        {options.isPending || options.error ? (
          <AdminState
            loading={options.isPending}
            error={options.error}
            onRetry={() => void options.refetch()}
          />
        ) : (
          <>
            <fieldset>
              <legend>Tòa nhà phụ trách</legend>
              <div className="ops-admin-check-list">
                {options.data?.buildings.map((building) => (
                  <label key={building.id}>
                    <Checkbox
                      aria-label={building.name}
                      checked={buildings.includes(building.id)}
                      onCheckedChange={() =>
                        toggle(building.id, buildings, setBuildings)
                      }
                    />
                    <span>{building.name}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>Dịch vụ phụ trách</legend>
              <div className="ops-admin-check-list">
                {options.data?.categories.map((category) => (
                  <label key={category.id}>
                    <Checkbox
                      aria-label={category.name}
                      checked={categories.includes(category.id)}
                      onCheckedChange={() =>
                        toggle(category.id, categories, setCategories)
                      }
                    />
                    <span>{category.name}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </>
        )}
        {create.error && (
          <p role="alert" className="ops-admin-error">
            {create.error.message}
          </p>
        )}
      </div>
    </AdminDrawer>
  );
}
