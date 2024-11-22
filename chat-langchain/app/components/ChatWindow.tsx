"use client";

import { Button, Image, Input, VStack, Text, Grid } from "@chakra-ui/react";
import React, { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RemoteRunnable } from "langchain/runnables/remote";
import { applyPatch } from "@langchain/core/utils/json_patch";

import { EmptyState } from "../components/EmptyState";
import { ChatMessageBubble, Message } from "../components/ChatMessageBubble";
import { AutoResizeTextarea } from "./AutoResizeTextarea";
import { marked } from "marked";
import { Renderer } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/gradient-dark.css";

import "react-toastify/dist/ReactToastify.css";
import {
	Heading,
	Flex,
	IconButton,
	InputGroup,
	InputRightElement,
	Spinner,
	Box,
} from "@chakra-ui/react";
import { ArrowUpIcon, CloseIcon, DeleteIcon } from "@chakra-ui/icons";
import { Select, Link } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { apiBaseUrl } from "../utils/constants";
import { ChatPromptValue } from "@langchain/core/prompt_values"
import { AIMessage, FunctionMessage, AIMessageChunk, FunctionMessageChunk } from "@langchain/core/messages"
import { forEach } from "lodash";
import { FaCircleNotch, FaTools, FaKeyboard, FaCheck } from 'react-icons/fa';
import { BiBot } from 'react-icons/bi';


const init_msg = "Please input your question."
const typing_msg = "Typing answer...."
const processing_msg = "Processing..."
const processing_end_msg = "Processing end."
const synthesizing_question_msg = "Synthesizing question..."
const invoking_tool_msg = "Invoking tool..."
function showProcessingTip(processingTip: string) {
	if (processingTip != "" && processingTip != init_msg) {
		return <Box className="whitespace-pre-wrap" color="green" padding={".2em"}>
			{processingTip}
		</Box>
	} else {
		return <Box className="whitespace-pre-wrap" color="red">
			{processingTip}
		</Box>
	}
}

enum ProcessingStatus {
	Idle = "idle",
	SynthesizingQuestion = "synthesizing_question",
	InvokingTool = "invoking_tool",
	Processing = "processing",
	Typing = "typing",
	Completed = "completed"
}

interface ImageFile {
	id: string;
	file: File;
	previewUrl: string;
	base64: string;
}

interface ImageUrl {
	id: string;
	url: string;
	base64: string;
}

export function ChatWindow(props: { conversationId: string }) {
	const conversationId = props.conversationId;

	const searchParams = useSearchParams();

	const messageContainerRef = useRef<HTMLDivElement | null>(null);
	const [messages, setMessages] = useState<Array<Message>>([]);
	const [input, setInput] = useState("");
	const [imageData, setImageData] = useState<string | null>(null);

	const [isLoading, setIsLoading] = useState(false);
	const [llm, setLlm] = useState(
		searchParams.get("llm") ?? "anthropic_claude_3_5_sonnet",
	);
	const [processingTip, setProcessingTip] = useState("Please input your question.")

	const [chatHistory, setChatHistory] = useState<
		{ type: string; content: string }[]
	>([]);

	const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>(ProcessingStatus.Idle);

	function showProcessingStatus(status: ProcessingStatus) {
		switch (status) {
			case ProcessingStatus.Idle:
				return null;
			case ProcessingStatus.SynthesizingQuestion:
				return (
					<div className="flex items-center text-blue-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>思考中</span>
					</div>
				);
			case ProcessingStatus.InvokingTool:
				return (
					<div className="flex items-center text-purple-500">
						<FaTools className="mr-2" size={20} />
						<span>调用工具</span>
					</div>
				);
			case ProcessingStatus.Processing:
				return (
					<div className="flex items-center text-orange-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>处理中</span>
					</div>
				);
			case ProcessingStatus.Typing:
				return (
					<div className="flex items-center text-green-500">
						<FaKeyboard className="mr-2" size={20} />
						<span>输入中</span>
					</div>
				);
			case ProcessingStatus.Completed:
				return (
					<div className="flex items-center text-green-500">
						<FaCheck className="mr-2" size={20} />
						<span>完成</span>
					</div>
				);
		}
	}

	const [imageFiles, setImageFiles] = useState<ImageFile[]>([]);
	const [imageUrls, setImageUrls] = useState<ImageUrl[]>([]);
	const [uploadType, setUploadType] = useState<"file" | "url">("file");
	const [isConverting, setIsConverting] = useState(false);

	const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
	const MAX_FILES = 5; // 最多上传5张图片

	const convertToBase64 = (file: File): Promise<string> => {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.readAsDataURL(file);
			reader.onload = () => {
				resolve(reader.result as string);
			};
			reader.onerror = error => reject(error);
		});
	};

	const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const files = event.target.files;
		if (!files) return;

		const totalImages = imageFiles.length + imageUrls.length;
		if (totalImages + files.length > MAX_FILES) {
			alert(`You can only upload up to ${MAX_FILES} images in total`);
			return;
		}

		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			if (file.size > MAX_FILE_SIZE) {
				alert(`File ${file.name} exceeds 5MB limit`);
				continue;
			}

			try {
				const previewUrl = URL.createObjectURL(file);
				const base64 = await convertToBase64(file);
				const newImageFile: ImageFile = {
					id: Math.random().toString(),
					file: file,
					previewUrl: previewUrl,
					base64: base64
				};
				setImageFiles(prev => [...prev, newImageFile]);
			} catch (error) {
				console.error("Error handling image:", error);
			}
		}
	};

	const urlToBase64 = async (url: string): Promise<string> => {
		try {
			const response = await fetch(url);
			const blob = await response.blob();
			return new Promise((resolve, reject) => {
				const reader = new FileReader();
				reader.onload = () => resolve(reader.result as string);
				reader.onerror = reject;
				reader.readAsDataURL(blob);
			});
		} catch (error) {
			console.error("Error converting URL to base64:", error);
			throw error;
		}
	};

	const isValidImageUrl = (url: string): boolean => {
		return /\.(jpg|jpeg|png|gif|webp)$/i.test(url);
	};

	const handleUrlInput = async (url: string) => {
		const totalImages = imageFiles.length + imageUrls.length;
		if (totalImages >= MAX_FILES) {
			alert(`You can only add up to ${MAX_FILES} images in total`);
			return;
		}

		if (url && isValidImageUrl(url)) {
			try {
				setIsConverting(true);
				const base64 = await urlToBase64(url);
				const newImageUrl: ImageUrl = {
					id: Math.random().toString(),
					url: url,
					base64: base64
				};
				setImageUrls(prev => [...prev, newImageUrl]);
			} catch (error) {
				console.error("Error converting URL to base64:", error);
				alert("Error loading image from URL");
			} finally {
				setIsConverting(false);
			}
		}
	};

	const removeImage = (id: string, type: "file" | "url") => {
		if (type === "file") {
			setImageFiles(prev => {
				const newFiles = prev.filter(img => img.id !== id);
				const removedFile = prev.find(img => img.id === id);
				if (removedFile) {
					URL.revokeObjectURL(removedFile.previewUrl);
				}
				return newFiles;
			});
		} else {
			setImageUrls(prev => prev.filter(img => img.id !== id));
		}
	};

	const clearAllImages = () => {
		imageFiles.forEach(img => URL.revokeObjectURL(img.previewUrl));
		setImageFiles([]);
		setImageUrls([]);
	};

	const sendMessage = async (message?: string) => {
		if (messageContainerRef.current) {
			messageContainerRef.current.classList.add("grow");
		}
		if (isLoading) {
			return;
		}
		const messageValue = message ?? input;
		if (messageValue === "") return;
		setInput("");
		setMessages((prevMessages) => [
			...prevMessages,
			{ id: Math.random().toString(), content: messageValue, role: "user" },
		]);
		setIsLoading(true);

		let accumulatedMessage = "";
		let runId: string | undefined = undefined;
		let sources: Source[] | undefined = undefined;
		let messageIndex: number | null = null;

		let renderer = new Renderer();
		renderer.paragraph = (text) => {
			return text + "\n";
		};
		renderer.list = (text) => {
			return `${text}\n\n`;
		};
		renderer.listitem = (text) => {
			return `\n• ${text}`;
		};
		renderer.code = (code, language) => {
			const validLanguage = hljs.getLanguage(language || "")
				? language
				: "plaintext";
			const highlightedCode = hljs.highlight(
				validLanguage || "plaintext",
				code,
			).value;
			return `<pre class="highlight bg-gray-700" style="padding: 5px; border-radius: 5px; overflow: auto; overflow-wrap: anywhere; white-space: pre-wrap; max-width: 100%; display: block; line-height: 1.2"><code class="${language}" style="color: #d6e2ef; font-size: 12px; ">${highlightedCode}</code></pre>`;
		};
		// 添加对原始 HTML 的支持
		renderer.html = (html) => {
			console.log(html)
			// 这里可以添加一些验证逻辑，例如只允许特定的 iframe
			if (html.startsWith('<iframe') && html.includes('musse.ai')) {
				return html;
			}
			// 对于其他 HTML，你可以选择返回空字符串、原始 HTML 或经过转义的 HTML
			return ''; // 或者 return html; 或者 return marked.escapeHtml(html);
		};
		marked.setOptions({ renderer });

		const allImages = [
			...imageFiles.map(img => img.base64),
			...imageUrls.map(img => img.base64)
		];
		try {
			const sourceStepName = "FindDocs";
			let streamedResponse: Record<string, any> = {};

			const remoteChain = new RemoteRunnable({
				url: process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL : "",
				options: {
					timeout: 3000000,
				},
			});
			const llmDisplayName = llm ?? "openai_gpt_3_5_turbo";
			const streams = await remoteChain.stream(
				{
					input: messageValue,
					// chat_history: chatHistory,
					chat_history: [],
					image_urls: allImages
				},
				{
					configurable: {
						llm: llmDisplayName,
					},
					tags: ["model:" + llmDisplayName],
					metadata: {
						conversation_id: conversationId,
						llm: llmDisplayName,
						is_multimodal: allImages.length > 0, // 当有图片时为 true
						images_size: allImages.length
					},
				},
				// {
				//   includeNames: [sourceStepName],
				// },
			);
			var chunk_buff = "";
			var buff_size = 100;
			var n = 0;
			for await (const chunk of streams) {
				console.log(chunk)
				var _chunk: object
				if (typeof chunk === "object") {
					_chunk = chunk as object;
					if ("run_id" in _chunk) {
						runId = _chunk.run_id as string;
					}
					var kind = "event" in _chunk ? _chunk.event : "";
					switch (kind) {
						case "on_chain_start":
							setProcessingStatus(ProcessingStatus.SynthesizingQuestion);
							break;
						case "on_chain_end":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chain_stream":
							break
						case "on_chat_model_start":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chat_model_end":
							setProcessingStatus(ProcessingStatus.Completed);
							break;
						case "on_chat_model_stream":
							setProcessingStatus(ProcessingStatus.Typing);
							if ("data" in _chunk) {
								var data = _chunk.data as object
								if ("chunk" in data && data.chunk instanceof AIMessageChunk) {
									var aichunk = data.chunk as AIMessageChunk;
									if (typeof (aichunk.content) == "string")
										accumulatedMessage += aichunk.content.toString();
									else if (Array.isArray(aichunk.content) && aichunk.content[0] && "text" in aichunk.content[0]) {
										var c_t = aichunk.content[0]['text'] as string;
										// const regex = /^<thinking>.*<\/thinking>$/;
										// if (!regex.test(c_t))
										accumulatedMessage += c_t;
										// else
										// 	console.log(c_t)
									}
									else
										console.log(_chunk)
								}
							}
							var parsedResult = marked.parse(accumulatedMessage);
							if (parsedResult != undefined) {
								setMessages((prevMessages) => {
									let newMessages = [...prevMessages];
									if (
										messageIndex === null ||
										newMessages[messageIndex] === undefined
									) {
										messageIndex = newMessages.length;
										newMessages.push({
											id: Math.random().toString(),
											content: parsedResult.trim(),
											runId: runId,
											sources: sources,
											role: "assistant",
										});
									} else if (newMessages[messageIndex] !== undefined) {
										newMessages[messageIndex].content = parsedResult.trim();
										newMessages[messageIndex].runId = runId;
										// newMessages[messageIndex].sources = sources;
									}
									return newMessages;
								});
							}
							break
						case "on_tool_start":
							setProcessingStatus(ProcessingStatus.InvokingTool);
							break;
						case "on_tool_end":
							setProcessingStatus(ProcessingStatus.Processing);
							// if ("name" in _chunk && _chunk.name == "googleSerperSearch") {
							// 	if ("data" in _chunk) {
							// 		var data = _chunk.data as object;
							// 		if ("output" in data) {
							// 			var output = eval('(' + data.output + ')');
							// 			sources = output.map((doc: Record<string, any>) => ({
							// 				url: doc.link,
							// 				title: doc.title,
							// 			}));
							// 		}
							// 	}
							// }
							let currentSources: Source[] = [];
							if ("name" in _chunk && _chunk.name == 'search') {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										var _output = data.output as Array<any>
										currentSources = _output.map((doc: Record<string, any>) => ({
											url: doc.value.url,
											title: doc.value.title,
											img_src: doc.value.imageUrl,
										}));
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "searchWebPageToAnswer" || _chunk.name == "searchNewsToAnswer")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										var output = eval('(' + data.output + ')') as object;
										if ("search_result" in output) {
											var search_result = output.search_result as Array<any>
											currentSources = search_result.map((doc: Record<string, any>) => ({
												url: doc.link,
												title: doc.title,
												img_src: doc.imageUrl,
											}));
										}
									}
								}
							}
							sources = [...sources ? sources : [], ...currentSources];
							setMessages((prevMessages) => {
								let newMessages = [...prevMessages];
								if (
									messageIndex === null ||
									newMessages[messageIndex] === undefined
								) {
									messageIndex = newMessages.length;
									newMessages.push({
										id: Math.random().toString(),
										content: parsedResult ? parsedResult.trim() : "",
										runId: runId,
										sources: sources,
										role: "assistant",
									});
								} else if (newMessages[messageIndex] !== undefined) {
									// newMessages[messageIndex].content = parsedResult.trim();
									newMessages[messageIndex].runId = runId;
									newMessages[messageIndex].sources = sources;
								}
								return newMessages;
							});
							break
						default:
							break
					}

				}
			}
			setChatHistory((prevChatHistory) => [
				...prevChatHistory,
				{ type: "human", content: messageValue },
				{ type: "ai", content: accumulatedMessage },
			]);
			setIsLoading(false);
			setProcessingStatus(ProcessingStatus.Idle);
		} catch (e) {
			setMessages((prevMessages) => prevMessages.slice(0, -1));
			setIsLoading(false);
			setInput(messageValue);
			setProcessingStatus(ProcessingStatus.Idle);
			throw e;
		} finally {
			// 消息发送后清理图片
			// clearAllImages();
		}
	};

	const sendInitialQuestion = async (question: string) => {
		await sendMessage(question);
	};

	const insertUrlParam = (key: string, value?: string) => {
		if (window.history.pushState) {
			const searchParams = new URLSearchParams(window.location.search);
			searchParams.set(key, value ?? "");
			const newurl =
				window.location.protocol +
				"//" +
				window.location.host +
				window.location.pathname +
				"?" +
				searchParams.toString();
			window.history.pushState({ path: newurl }, "", newurl);
		}
	};

	return (
		<div className="flex flex-col items-center p-8 rounded grow max-h-full">
			<Flex
				direction={"column"}
				alignItems={"center"}
				marginTop={messages.length > 0 ? "" : "64px"}
			>
				<Heading
					fontSize={messages.length > 0 ? "2xl" : "3xl"}
					fontWeight={"medium"}
					mb={1}
					color={"white"}
				>
					🍺 Ethereum Address Analysis 🥩
				</Heading>
				<Heading
					fontSize="xl"
					fontWeight={"normal"}
					color={"white"}
					marginTop={"10px"}
					textAlign={"center"}
				>
					Ask me anything!{" "}
				</Heading>

				<div className="text-white flex flex-wrap items-center mt-4">
					<div className="flex items-center mb-2">
						<span className="shrink-0 mr-2">Powered by</span>
						<Select
							value={llm}
							onChange={(e) => {
								insertUrlParam("llm", e.target.value);
								setLlm(e.target.value);
							}}
							width={"240px"}
						>
							{/* <option value="anthropic_claude_3_opus">Anthropic-Claude-3-Opus</option> */}
							{/* <option value="openai_gpt_4_turbo_preview">GPT-4-Turbo</option> */}
							<option value="anthropic_claude_3_5_sonnet">Anthropic-Claude-3.5-Sonnet</option>
							<option value="openai_gpt_4o">GPT-4o</option>
							<option value="openai_gpt_4o_mini">GPT-4o-mini</option>
							{/* <option value="openai_gpt_3_5_turbo_1106">GPT-3.5-Turbo</option> */}
							{/* <option value="pplx_sonar_medium_chat">PPLX_sonar_medium_chat</option> */}
							{/* <option value="mistral_large">Mistral-Large</option> */}
							{/* <option value="command_r_plus">Command R+</option> */}
						</Select>
					</div>
				</div>
				<div className="ml-4">
					{showProcessingStatus(processingStatus)}
				</div>
			</Flex>
			<div
				className="flex flex-col-reverse w-full mb-2 overflow-auto"
				ref={messageContainerRef}
			>
				{
					[...messages]
						.reverse()
						.map((m, index) => (
							<ChatMessageBubble
								key={m.id}
								message={{ ...m }}
								aiEmoji="🦜"
								isMostRecent={index === 0}
								messageCompleted={!isLoading}
							></ChatMessageBubble>
						))
				}
			</div>
			<Flex direction="column" width="100%" mb={4}>
				<Select
					value={uploadType}
					onChange={(e) => {
						setUploadType(e.target.value as "file" | "url");
					}}
					mb={2}
					color="white"
				>
					<option value="file">Upload Image Files</option>
					<option value="url">Input Image URLs</option>
				</Select>

				{uploadType === "file" ? (
					<InputGroup>
						<input
							type="file"
							accept="image/*"
							onChange={handleFileUpload}
							style={{ display: 'none' }}
							id="image-upload"
							multiple
						/>
						<Button
							as="label"
							htmlFor="image-upload"
							colorScheme="blue"
							width="100%"
							isDisabled={imageFiles.length + imageUrls.length >= MAX_FILES}
						>
							Choose Image Files ({imageFiles.length + imageUrls.length}/{MAX_FILES})
						</Button>
					</InputGroup>
				) : (
					<VStack spacing={2} width="100%">
						<InputGroup>
							<Input
								placeholder="Enter image URL"
								color="white"
								onKeyDown={(e) => {
									if (e.key === 'Enter') {
										const input = e.target as HTMLInputElement;
										handleUrlInput(input.value);
										input.value = '';
									}
								}}
								isDisabled={isConverting || imageFiles.length + imageUrls.length >= MAX_FILES}
							/>
							{isConverting && (
								<InputRightElement>
									<Spinner size="sm" />
								</InputRightElement>
							)}
						</InputGroup>
						<Text fontSize="sm" color="gray.400">
							Press Enter to add URL ({imageFiles.length + imageUrls.length}/{MAX_FILES})
						</Text>
					</VStack>
				)}

				{/* 图片预览网格 */}
				{(imageFiles.length > 0 || imageUrls.length > 0) && (
					<Box mt={4} position="relative">
						{/* 图片预览区域的容器 */}
						<Box
							position="relative"
							borderWidth="1px"
							borderColor="gray.600"
							borderRadius="md"
							p={4}
						>
							{/* Clean All 按钮放在右上角 */}
							<Flex
								position="absolute"
								top={2}
								right={2}
								zIndex={2}
							>
								<Button
									leftIcon={<DeleteIcon />}
									size="sm"
									variant="solid"
									colorScheme="red"
									onClick={clearAllImages}
									transition="all 0.2s"
									_hover={{
										transform: 'scale(1.05)',
										bg: 'red.600'
									}}
									_active={{
										bg: 'red.700'
									}}
									borderRadius="md"
									px={4}
									opacity={0.9}
									backdropFilter="blur(8px)"
								>
									Clear All ({imageFiles.length + imageUrls.length})
								</Button>
							</Flex>

							{/* 图片网格 */}
							<Grid
								templateColumns="repeat(auto-fill, minmax(150px, 1fr))"
								gap={4}
								mt={2}
							>
								{imageFiles.map((img) => (
									<Box key={img.id} position="relative">
										<Image
											src={img.previewUrl}
											alt="Preview"
											maxH="150px"
											objectFit="contain"
											width="100%"
											borderRadius="md"
										/>
										<IconButton
											aria-label="Remove image"
											icon={<CloseIcon />}
											size="sm"
											position="absolute"
											top={1}
											right={1}
											onClick={() => removeImage(img.id, "file")}
										/>
									</Box>
								))}
								{imageUrls.map((img) => (
									<Box key={img.id} position="relative">
										<Image
											src={img.url}
											alt="Preview"
											maxH="150px"
											objectFit="contain"
											width="100%"
											borderRadius="md"
										/>
										<IconButton
											aria-label="Remove image"
											icon={<CloseIcon />}
											size="sm"
											position="absolute"
											top={1}
											right={1}
											onClick={() => removeImage(img.id, "url")}
										/>
									</Box>
								))}
							</Grid>
						</Box>
					</Box>
				)}
			</Flex>
			<InputGroup size="md" alignItems={"center"}>
				<AutoResizeTextarea
					value={input}
					maxRows={5}
					marginRight={"56px"}
					placeholder="Hello, World!"
					textColor={"white"}
					borderColor={"rgb(58, 58, 61)"}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === "Enter" && !e.shiftKey) {
							e.preventDefault();
							sendMessage();
						} else if (e.key === "Enter" && e.shiftKey) {
							e.preventDefault();
							setInput(input + "\n");
						}
					}}
				/>
				<InputRightElement h="full">
					<IconButton
						colorScheme="blue"
						rounded={"full"}
						aria-label="Send"
						icon={isLoading ? <Spinner /> : <ArrowUpIcon />}
						type="submit"
						onClick={(e) => {
							e.preventDefault();
							sendMessage();
						}}
					/>
				</InputRightElement>
			</InputGroup>
		</div>
	);
}
