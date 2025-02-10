"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react"
import { ethers } from 'ethers'
import UniversalProvider from '@walletconnect/universal-provider'
import { useState } from "react";
import { ButtonGroup, Button, Tooltip } from '@chakra-ui/react'
import { mainnet, bsc, tron, arbitrum, sepolia, solana, solanaTestnet, solanaDevnet } from '@reown/appkit/networks'
import type { AppKitNetwork } from '@reown/appkit-common';
import { wcModal } from "../context/appkit";
// import { useSendTransaction } from 'wagmi'


// 修改组件定义,接收并使用 children 属性
export function SendEVMTransaction(props: { txData: any, name: string | undefined }) {
	const [isShow, setShow] = useState(true)
	const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
	const { walletProvider } = useAppKitProvider('eip155')
	const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()
	const { open, close } = useAppKit();
	const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, tron, arbitrum, sepolia, solana];
	const [isLoading, setLoading] = useState<boolean>(false);

	// 优化: 统一管理按钮禁用状态
	const isDisabled = isLoading || !isConnected || !walletProvider || !props.txData;
	const getDisabledReason = () => {
		if (isLoading) return 'Transaction in progress...';
		if (!isConnected) return 'Please connect your wallet first';
		if (!walletProvider) return 'Wallet provider not ready';
		if (!props.txData) return 'Transaction data not available';
		return '';
	};

	const signAndSendTransaction = async () => {
		if (!isConnected) {
			await open({ view: "Connect" });
			return;
		}
		if (!isLoading) {
			try {
				setLoading(true);
				console.log("Wallet connected?" + isConnected)
				let curNet = null;
				for (let i = 0; i < networks.length; i++) {
					if (networks[i].id === chainId) {
						curNet = networks[i];
						break;
					}
				}
				if (curNet)
					wcModal.switchNetwork(curNet)
				// const provider = new ethers.providers.(walletProvider as UniversalProvider)
				const provider = new ethers.providers.Web3Provider(walletProvider as UniversalProvider)
				const signer = provider.getSigner(address)
				// await provider.connect()
				// let signer = await provider.getSigner(address)
				// Construct transaction object
				const transaction = {
					from: address,
					to: props.txData.to,
					data: props.txData.data,
					value: props.txData.value,
					gasLimit: props.txData.gasLimit,
					gasPrice: props.txData.gasPrice,
					chainId: chainId as number,
				};

				// Send transaction
				// const tx = await provider.request({ "method": "eth_sendTransaction", "params": transaction }, chainId?.toString()) as any;
				const tx = await signer.sendTransaction(transaction)
				// await sendTransaction(transaction)
				console.log('Transaction hash:', tx.hash);

				// Wait for transaction confirmation
				const receipt = await tx.wait();
				console.log('Transaction confirmed:', receipt);
				// setShow(false)
				setLoading(false)
			} catch (e) {
				console.log(e)
			} finally {
				setLoading(false)
			}
		}
	}

	return isShow && (
		<Tooltip label={isDisabled ? getDisabledReason() : ''}>
			<Button onClick={async () => await signAndSendTransaction()} disabled={isDisabled}>
				{props.name}
			</Button>
		</Tooltip>
	);
}
