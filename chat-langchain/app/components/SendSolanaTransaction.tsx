"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit, useWalletInfo } from "@reown/appkit/react"
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import type { Provider } from '@reown/appkit-adapter-solana'
import {
	SystemProgram,
	PublicKey,
	Keypair,
	Transaction,
	TransactionInstruction,
	LAMPORTS_PER_SOL
} from '@solana/web3.js'
import { useState } from "react";
import { ButtonGroup, Button, Tooltip } from '@chakra-ui/react'

import { wcModal } from "../context/appkit"
import { solana } from "@reown/appkit/networks";


// 修改组件定义,接收并使用 children 属性
export function SendSolanaTransaction(props: { txData: any, name: string | undefined }) {
	const [isShow, setShow] = useState(true)
	const { walletProvider } = useAppKitProvider<Provider>('solana')
	const { connection } = useAppKitConnection()
	const { open, close } = useAppKit();
	const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
	const [isLoading, setLoading] = useState<boolean>(false);
	const isDisabled = isLoading || !isConnected || !connection || !props.txData;

	// Get disabled reason for tooltip
	const getDisabledReason = () => {
		if (isLoading) return 'Transaction is in progress...';
		if (!isConnected) return 'Please connect your wallet first';
		if (!connection) return 'Waiting for network connection...';
		if (!props.txData) return 'Transaction data is not ready';
		return '';
	}
	const signAndSendTransaction = async () => {
		if (!isLoading) {
			try {
				setLoading(true);
				if (!connection) {
					await wcModal.switchNetwork(solana)
					// await open({ view: 'Connect' })
				}
				// 1. 创建Transaction实例
				const transaction = new Transaction();
				console.log(props.txData)

				// 2. 遍历tx数组,构建每个TransactionInstruction
				for (const instruction of props.txData.tx) {
					// 2.1 处理account keys
					const keys = instruction.keys.map((key: any) => ({
						pubkey: new PublicKey(key.pubkey),
						isSigner: key.isSigner,
						isWritable: key.isWritable
					}));

					// 2.2 转换programId
					const programId = new PublicKey(instruction.programId);

					// 2.3 将data数组转为Buffer
					const data = Buffer.from(instruction.data);

					// 2.4 创建TransactionInstruction
					const txInstruction = new TransactionInstruction({
						keys,
						programId,
						data
					});

					// 2.5 添加指令到Transaction
					transaction.add(txInstruction);
				}
				if (connection) {
					const { blockhash } = await connection.getLatestBlockhash();
					transaction.recentBlockhash = blockhash;
					transaction.feePayer = new PublicKey(address as any);
					if (props.txData.signer) {
						const privateKey = Uint8Array.from(props.txData.signer);
						const signer = Keypair.fromSecretKey(privateKey);
						transaction.sign(signer);
					}
					// First sign the transaction
					const signedTx = await walletProvider.sendTransaction(transaction, connection);
					// Then send the signed transaction
					// const tx = await connection.sendRawTransaction(signedTx.serialize());
					console.log(signedTx)
					// setShow(false)
				} else {
					console.log("solana provider connection is " + connection)
				}
			} catch (e) {
				console.log(e)
			} finally {
				setLoading(false)
			}
		}
	}
	return isShow && <Tooltip label={isDisabled ? getDisabledReason() : ''}>
		<Button onClick={async () => await signAndSendTransaction()} disabled={isLoading}>{props.name}</Button>
	</Tooltip>
}