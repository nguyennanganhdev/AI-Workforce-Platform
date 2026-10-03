import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { client } from "@/lib/client";
import type { VinhomesTicketSummary } from "../../../../../shared/vinhomes-ticket";

export function LiveTicketInbox() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["vinhomes", "tickets"],
    queryFn: () =>
      client<VinhomesTicketSummary[]>("/api/vinhomes/tickets", "tickets", {
        fallback: "Không tải được yêu cầu.",
      }),
    retry: false,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Yêu cầu cư dân</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p>Đang tải yêu cầu...</p>
        ) : error ? (
          <div className="flex items-center gap-3">
            <p role="alert">{error.message}</p>
            <Button
              type="button"
              variant="outline"
              onClick={() => void refetch()}
            >
              Thử lại
            </Button>
          </div>
        ) : data?.length === 0 ? (
          <p>Chưa có yêu cầu trong phạm vi quản lý của bạn.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mã</TableHead>
                <TableHead>Yêu cầu</TableHead>
                <TableHead>Mức độ</TableHead>
                <TableHead>Ưu tiên</TableHead>
                <TableHead>Đánh giá</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead>Tiếp nhận</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((ticket) => (
                <TableRow key={ticket.id}>
                  <TableCell>{ticket.code}</TableCell>
                  <TableCell>{ticket.title}</TableCell>
                  <TableCell>{ticket.severity}</TableCell>
                  <TableCell>{ticket.priority ?? "Chờ đánh giá"}</TableCell>
                  <TableCell>{ticket.triageStatus}</TableCell>
                  <TableCell>{ticket.status}</TableCell>
                  <TableCell>
                    {new Date(ticket.createdAt).toLocaleString("vi-VN")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {data?.length === 50 && (
          <p className="mt-3 text-sm text-muted-foreground">
            Đang hiển thị 50 yêu cầu gần nhất.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
