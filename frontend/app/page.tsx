import { Suspense } from "react";
import { Dashboard, DashboardSkeleton } from "@/components/Dashboard";

export default function Page() {
  // Dashboard reads ?sort= and ?status= (useSearchParams), which needs a Suspense boundary.
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <Dashboard />
    </Suspense>
  );
}
