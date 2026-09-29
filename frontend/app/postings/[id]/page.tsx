import { PostingView } from "@/components/PostingView";

export default async function PostingPage(props: PageProps<"/postings/[id]">) {
  const { id } = await props.params;
  const { existing } = await props.searchParams;
  return <PostingView id={id} existing={existing === "1"} />;
}
