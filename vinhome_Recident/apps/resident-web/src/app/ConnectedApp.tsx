import { App } from "./App";
import { useConnectedResident } from "../services/use-connected-resident";

export function ConnectedApp() {
  const live = useConnectedResident();
  return <App live={live} />;
}
