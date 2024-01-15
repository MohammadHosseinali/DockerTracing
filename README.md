# DockerTracing

In this project we will trace docker networking modes and compare the difference between them and normal networking mode based on kernel functions.

# Tools

1.Custom python script to create TCP traffic flow between client container and server container (files are available on repo)

2.Perf

3.Ftrace

# Setup and config:

```
sudo apt install docker.io -y
git clone https://github.com/MohammadHosseinali/DockerTracing
cd DockerTracing/
docker build . -t mypython3
```

# Bridge Mode
Docker default networking uses a bridge network driver, which creates a virtual network bridge on the host system and assigns an IP address to each container connected to the bridge. Containers on the same bridge network can communicate with each other using internal IP addresses, but they are isolated from containers on different bridge networks.

By default, when you start Docker, a default bridge network (also called bridge) is created automatically, and newly-started containers connect to it unless otherwise specified. You can also create user-defined custom bridge networks, which have some advantages over the default bridge network, such as automatic DNS resolution between containers, better isolation, and more flexibility.

To create a bridge network, you can use the following commands:

```
docker run -itd --rm --name c1 mypython3
docker run -itd --rm --name c2 mypython3
docker exec -it c1 python app/server.py
```

Open another terminal and run:
```
docker exec -it c2 python app/client.py 172.17.0.2
```

This will create a TCP traffic flow. Now we run the command below to capture kernel events:

```
sudo perf record -ae 'net:*' --call-graph fp -- sleep 5
sudo perf script > bridge.txt
```

Now we run the same command outside of docker container:

```
python app/server.py & python app/client.py 127.0.0.1
sudo perf record -ae 'net:*' --call-graph fp -- sleep 5
sudo perf script > normal.txt
```
**Normal connection:**

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/e1298fa8-8133-4637-84e6-4188c8c6123c)


**Docker bridge:**

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/56a2f441-21ba-4da4-b75b-617d7c0eca0c)

As we can see, there are extra br_ functions in docker bridge mode
Now let's check the kernel codes to see what does each function do:

- `br_dev_queue_push_xmit`: Pushes a packet to the network interface queue for transmission.
- `br_nf_post_routing`: Applies the netfilter post-routing hooks to a packet after it has been forwarded by the bridge.
- `br_forward_finish`: Performs some final operations on a packet before forwarding it, such as updating the statistics and freeing the skb.
- `br_nf_forward_finish`: A callback function that is invoked after the netfilter forward hooks have been applied to a packet.
- `br_nf_forward_ip`: A helper function that checks the IP header and checksum of a packet before forwarding it.
- `__br_forward`: The main function that forwards a packet to a given destination port.
- `br_handle_frame_finish`: A callback function that is invoked after the netfilter pre-routing hooks have been applied to a packet.
- `br_nf_pre_routing_finish`: A helper function that performs some checks and operations on a packet before routing it.
- `br_nf_pre_routing`: Applies the netfilter pre-routing hooks to a packet before it is routed by the bridge.
- `br_handle_frame`: The entry point for handling a packet received by the bridge.

In order to understand how does `br_dev_queue_push_xmit` works, we will use a function graph:

```
sudo su
```

```
cd /sys/kernel/tracing
echo br_dev_queue_push_xmit > set_graph_function
echo function_graph > current_tracer
echo 1 > tracing_on
```
And stop tracing:
```
echo 0 > tracing_on
```
The graph shows the time spent in each function call and the nested calls within them. So let's explain what's happening:

`br_dev_queue_push_xmit` is the entry point for the bridge device transmission. It checks the packet size and checksum, and then pushes the Ethernet header to the packet. It also calls `dev_queue_xmit` to queue the packet for the network device.
`__dev_queue_xmit` performs some validations and adjustments on the packet, such as checking the fragmentation. It also invokes the `dev_hard_start_xmit` function to start which is the function that calls the device driver's `hard_start_xmit` routine to send the packet. In this case, the device driver is `veth`, which is a virtual Ethernet pair device, therefore, `veth_xmit` forwards the packet to the `veth` device by cloning the timestamp and calling `__dev_forward_skb`. It also calls `__netif_rx` to deliver the packet to the network stack of the peer device.
`__dev_forward_skb` is a helper function that forwards a packet to another device by scrubbing the packet and changing the Ethernet type.

`__netif_rx` is the function that receives a packet from a device and passes it to the network stack. It calls `netif_rx_internal` which is a function that enqueues a packet to the backlog queue of the current CPU. It acquires and releases a spin lock to protect the queue, and increments and decrements the preempt count to disable and enable preemption.


**Performance difference:**

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/a203dd96-ee8c-4adf-af32-afd14b2d170d)

As we can see, the performance is about 1.6x better in normal connection mode which makes sense.


	
# MACVLAN:
Docker MACVLAN networking works by assigning a unique MAC address to each container's virtual network interface, making it appear to be a physical device on the network. This allows the containers to communicate with other devices on the same network, without using NAT or port mapping.

To create a MACVLAN network, you need to specify the driver, the subnet, the gateway, and the parent interface. You can also use the ip-range and aux-addresses options to exclude some IP addresses from being used by the containers. For example, to create a MACVLAN network, First you need to choose an unused ip from your router ip range and you can use these variables:

```
YOUR_SUBNET=192.168.8.0/24        # your network subnet 
YOUR_GATEWAY=192.168.8.1          # your router gateway
CUSTOM_IP_ADDRESS=192.168.8.245    # server ip
CUSTOM_IP_ADDRESS_2=192.168.8.246    # client ip
```

To create a docker network on your subnet (Your VM should be on bridge mode):
```
docker network create -d macvlan --subnet $YOUR_SUBNET --gateway $YOUR_GATEWAY -o parent=enp0s3 my_macvlan
docker run -itd --rm --network my_macvlan --ip $CUSTOM_IP_ADDRESS --name c3 mypython3
docker run -itd --rm --network my_macvlan --ip $CUSTOM_IP_ADDRESS_2 --name c4 mypython3
docker exec -it c3 python app/server.py
```

Now to create TCP traffic flood, use the command below on another terminal:
```
docker exec -it c4 python app/client.py $CUSTOM_IP_ADDRESS
```

Start tracing and save results into a text file:
```
sudo perf record -ae 'net:*' --call-graph fp -- sleep 5
sudo perf script > macVLAN.txt
```

There is not much of a difference in called functions, except in start_xmit methods:

Normal mode:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/58a5d5db-a10b-4f55-9d56-92c4e383252d)

MACVLAN mode:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/2bb3a234-820e-4825-8540-324b667f52e0)

As we can see, normal networking contains `loopback_xmit` but MACVLAN has a `macvlan_start_xmit`

The definition is in /drivers/net/macvlan.c:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/13e1ea55-026b-4eb4-a82e-81f50b5f0156)

The code above first checks if netpoll is enabled (a mechanism for drivers to send and receive without interrupt). If it was, use this mechanism to send packet. Otherwise, put the packet in macvlan queue and if status is successful or is in congestion(CN) then increase number of sent packets and sent bytes pointer. Otherwise increase pointer of dropped packets. 

**Performance:**
There is not much performance difference between this mode and previous (bridge) mode:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/70d3771a-1daf-4dc4-a276-0465eaf33b29)


# IPVLAN (L3):
Docker IPVLAN networking works by creating a virtual network interface for each container that shares the same MAC address and IP address range as the parent interface on the host. This allows the containers to communicate with other devices on the same network without using NAT or port mapping.

There are two modes of IPVLAN networking: L2 and L3. In L2 mode, the containers use ARP to resolve the IP addresses of other devices on the network. In L3 mode, the containers use IP routing to forward packets to other devices on the network.

To create an ipvlan network, first you need to remove previous network:
```
YOUR_SUBNET=192.168.8.0/24
YOUR_GATEWAY=192.168.8.1
CUSTOM_IP_ADDRESS=192.168.8.245
CUSTOM_IP_ADDRESS_2=192.168.8.246
docker stop c3 c4
docker network rm my_macvlan
docker network create -d ipvlan --subnet $YOUR_SUBNET --gateway $YOUR_GATEWAY -o parent=enp0s3 my_ipvlan
```

Then, you need to specify the driver, the subnet, the gateway, and the parent interface. For example, to create an IPVLAN network named my_ipvlan, associated with the enp0s3 interface on the Docker host, you can use the following command:

```
docker run -itd --rm --network my_ipvlan --ip $CUSTOM_IP_ADDRESS --name c5 mypython3
docker run -itd --rm --network my_ipvlan --ip $CUSTOM_IP_ADDRESS_2 --name c6 mypython3
docker exec -it c5 python app/server.py
```


Now run the commands below in another terminal to flood tcp messages:
```
docker exec -it c6 python app/client.py $CUSTOM_IP_ADDRESS
```

Then start tracing and save results to a text file:
```
sudo perf record -ae 'net:*' --call-graph fp -- sleep 5
sudo perf script > ipVLAN.txt
```

The difference here is in `ipvlan_start_xmit`, `ipvlan_queue_xmit`, `ipvlan_rcv_frame` functions:

Normal mode:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/58a5d5db-a10b-4f55-9d56-92c4e383252d)

IPVLAN:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/e2caa479-b8c1-49ee-b360-c47710c0b5e2)

based on kernel codes:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/9d66c714-5367-48ea-b4bc-9f845482f3e3)

as we can see, `ipvlan_start_xmit` is exactly like `macvlan_start_xmit` that we described earlier, except it doesn't use netpoll mechanism.

now for `ipvlan_queue_xmit`:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/2ad4ab13-40e6-4989-89a3-6193a54b12ed)

The function first gets the IPVLAN device and port information from the net_device structure, and checks if they are valid. If not, it frees the sk_buff structure and returns NET_XMIT_DROP, which indicates that the packet transmission failed.

Then, the function checks if the sk_buff structure has enough data to pull out an Ethernet header, which is needed to determine the destination MAC address of the packet. If not, it also frees the sk_buff structure and returns NET_XMIT_DROP.

Next, the function switches on the mode of the IPVLAN port, which can be either IPVLAN_MODE_L2, IPVLAN_MODE_L3, or IPVLAN_MODE_L3S. These modes determine how the IPVLAN device handles the packet forwarding and routing. Depending on the mode, the function calls either ipvlan_xmit_mode_l2 or ipvlan_xmit_mode_l3, which are helper functions that implement the specific logic for each mode. These functions return either NET_XMIT_SUCCESS, which indicates that the packet transmission succeeded, or NET_XMIT_DROP, which indicates that the packet transmission failed.

Finally, the function has a default case that should not be reached, as it means that the IPVLAN port has an invalid mode. In this case, the function prints a warning message.

**Performance:**
The performance of IPVLAN mode is significantly worse than any other mode:

![image](https://github.com/MohammadHosseinali/DockerTracing/assets/57370539/80de3909-85ad-4b96-987e-a11ea32a0bb3)

As we can see IPVLAN mode could only send about 5000 packets which is 6x lower than normal networking mode.


