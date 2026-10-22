import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, workspaceApi } from "../api";
import type { EntityKind, MapNode, NetworkOptions, NetworkType, ScienceMap } from "../types";
import { NetworkCanvas, clusterColor } from "./NetworkCanvas";

const NORMALIZATIONS = ["association", "inclusion", "none"] as const;

const DEFAULTS: NetworkOptions = {
  type: "co_occurrence",
  unit: "keyword",
  min_occurrences: 5,
  min_shared: 2,
  normalization: "association",
  resolution: 1,
  min_cluster_size: 1,
  max_nodes: 1000,
  max_edges: 2000,
};

export function MapPanel({ workspaceId, version }: { workspaceId: string; version: number }) {
  const { t } = useTranslation();
  const [units, setUnits] = useState<Record<NetworkType, EntityKind[]> | null>(null);
  const [options, setOptions] = useState<NetworkOptions>(DEFAULTS);
  const [map, setMap] = useState<ScienceMap | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapNode | null>(null);
  const [showLabels, setShowLabels] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    void workspaceApi.networkUnits(workspaceId).then(setUnits);
  }, [workspaceId]);

  // The dataset changed underneath: the drawn map no longer matches it.
  useEffect(() => {
    setMap(null);
    setSelected(null);
  }, [version]);

  const build = useCallback(
    async (next: NetworkOptions) => {
      setBusy(true);
      setError(null);
      try {
        setMap(await workspaceApi.map(workspaceId, next));
        setSelected(null);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("import.errorGeneric"));
      } finally {
        setBusy(false);
      }
    },
    [workspaceId, t],
  );

  function changeType(type: NetworkType) {
    const allowed = units?.[type] ?? [];
    setOptions((o) => ({ ...o, type, unit: allowed.includes(o.unit) ? o.unit : allowed[0] }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void build(options);
  }

  const allowedUnits = units?.[options.type] ?? [];
  const needsShared =
    options.type === "bibliographic_coupling" || options.type === "co_citation";

  return (
    <section>
      <h2>{t("map.heading")}</h2>
      <p className="muted">{t("map.help")}</p>

      <form className="query-form" onSubmit={submit}>
        <label>
          {t("map.type")}
          <select value={options.type} onChange={(e) => changeType(e.target.value as NetworkType)}>
            {Object.keys(units ?? {}).map((type) => (
              <option key={type} value={type}>
                {t(`map.types.${type}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("map.unit")}
          <select
            value={options.unit}
            onChange={(e) => setOptions((o) => ({ ...o, unit: e.target.value as EntityKind }))}
          >
            {allowedUnits.map((unit) => (
              <option key={unit} value={unit}>
                {t(`map.units.${unit}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("map.minOccurrences")}
          <input
            type="number"
            min={1}
            value={options.min_occurrences}
            onChange={(e) =>
              setOptions((o) => ({ ...o, min_occurrences: Number(e.target.value) || 1 }))
            }
          />
        </label>
        {needsShared && (
          <label>
            {t("map.minShared")}
            <input
              type="number"
              min={1}
              value={options.min_shared}
              onChange={(e) =>
                setOptions((o) => ({ ...o, min_shared: Number(e.target.value) || 1 }))
              }
            />
          </label>
        )}
        <label>
          {t("map.normalization")}
          <select
            value={options.normalization}
            onChange={(e) =>
              setOptions((o) => ({
                ...o,
                normalization: e.target.value as NetworkOptions["normalization"],
              }))
            }
          >
            {NORMALIZATIONS.map((n) => (
              <option key={n} value={n}>
                {t(`map.normalizations.${n}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("map.resolution")}
          <input
            type="number"
            min={0.1}
            max={5}
            step={0.1}
            value={options.resolution}
            onChange={(e) =>
              setOptions((o) => ({ ...o, resolution: Number(e.target.value) || 1 }))
            }
          />
        </label>
        <label>
          {t("map.minClusterSize")}
          <input
            type="number"
            min={1}
            value={options.min_cluster_size}
            onChange={(e) =>
              setOptions((o) => ({ ...o, min_cluster_size: Number(e.target.value) || 1 }))
            }
          />
        </label>
        <label>
          {t("map.maxEdges")}
          <input
            type="number"
            min={100}
            max={50000}
            value={options.max_edges}
            onChange={(e) =>
              setOptions((o) => ({ ...o, max_edges: Number(e.target.value) || 2000 }))
            }
          />
        </label>
        <label>
          {t("map.maxNodes")}
          <input
            type="number"
            min={10}
            max={10000}
            value={options.max_nodes}
            onChange={(e) =>
              setOptions((o) => ({ ...o, max_nodes: Number(e.target.value) || 1000 }))
            }
          />
        </label>
        <div className="wide">
          <button type="submit" disabled={busy}>
            {busy ? t("map.building") : t("map.build")}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {map && (
        <>
          <p className="summary">
            {t("map.summary", {
              nodes: map.nodes.length,
              edges: map.edges.length,
              clusters: map.clusters,
              modularity: map.modularity.toFixed(3),
            })}
          </p>
          {map.truncated_from && (
            <p className="muted">
              {t("map.truncated", { shown: map.nodes.length, total: map.truncated_from })}
            </p>
          )}
          {map.edges_before_limit && (
            <p className="muted">
              {t("map.edgesLimited", {
                shown: map.edges.length,
                total: map.edges_before_limit,
              })}
            </p>
          )}
          {map.nodes.length === 0 ? (
            <p className="muted">{t("map.empty")}</p>
          ) : (
            <>
              <div className="map-toolbar">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={showLabels}
                    onChange={(e) => setShowLabels(e.target.checked)}
                  />
                  {t("map.labels")}
                </label>
                <label className="check">
                  {t("map.search")}
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <span className="muted">{t("map.hint")}</span>
              </div>
              <div className="map-area">
                <NetworkCanvas
                  map={map}
                  showLabels={showLabels}
                  highlight={search.trim() || null}
                  onSelect={setSelected}
                />
                <aside className="map-side">
                  <h4>{t("map.legend")}</h4>
                  <ul className="legend">
                    {Array.from({ length: map.clusters }, (_, i) => i + 1).map((cluster) => (
                      <li key={cluster}>
                        <span className="swatch" style={{ background: clusterColor(cluster) }} />
                        {cluster} ({map.nodes.filter((n) => n.cluster === cluster).length})
                      </li>
                    ))}
                  </ul>
                  {selected && (
                    <dl className="metrics selected">
                      <div className="metric">
                        <dt>{selected.label}</dt>
                        <dd />
                      </div>
                      <div className="metric">
                        <dt>{t("map.node.documents")}</dt>
                        <dd>{selected.documents}</dd>
                      </div>
                      <div className="metric">
                        <dt>{t("map.node.citations")}</dt>
                        <dd>{selected.citations}</dd>
                      </div>
                      <div className="metric">
                        <dt>{t("map.node.links")}</dt>
                        <dd>{selected.link_strength}</dd>
                      </div>
                      <div className="metric">
                        <dt>{t("map.node.cluster")}</dt>
                        <dd>{selected.cluster}</dd>
                      </div>
                      {selected.year !== null && (
                        <div className="metric">
                          <dt>{t("map.node.year")}</dt>
                          <dd>{selected.year}</dd>
                        </div>
                      )}
                    </dl>
                  )}
                </aside>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
