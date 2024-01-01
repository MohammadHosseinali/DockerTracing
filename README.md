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
docker exec -it c2 bash 
python app/client.py 172.17.0.2/16
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

	

	
# macVLAN:
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



# IPVLAN Mode (L3):
Docker IPVLAN networking works by creating a virtual network interface for each container that shares the same MAC address and IP address range as the parent interface on the host. This allows the containers to communicate with other devices on the same network without using NAT or port mapping.

There are two modes of IPVLAN networking: L2 and L3. In L2 mode, the containers use ARP to resolve the IP addresses of other devices on the network. In L3 mode, the containers use IP routing to forward packets to other devices on the network.

To create an ipvlan network, first you need to remove previous network:
```
docker stop c3 c4
docker network rm my_macvlan
docker network create -d ipvlan --subnet $YOUR_SUBNET --gateway $YOUR_GATEWAY -o parent=enp0s3 my_ipvlan
```

Then, you need to specify the driver, the subnet, the gateway, and the parent interface. For example, to create an IPVLAN network named my_ipvlan, associated with the enp0s3 interface on the Docker host, you can use the following command:

```
YOUR_SUBNET=192.168.8.0/24
YOUR_GATEWAY=192.168.8.1
CUSTOM_IP_ADDRESS=192.168.8.245
CUSTOM_IP_ADDRESS_2=192.168.8.246
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
